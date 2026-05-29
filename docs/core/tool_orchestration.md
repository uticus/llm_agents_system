# tool_orchestration

## Overview

The `tool_orchestration` module provides the full lifecycle for agent tool use: defining tools, registering them by name, validating model-requested arguments against a JSON-Schema-subset specification, executing tool callables (both async and sync), and returning structured results. It exists so that the rest of the system has a single, well-defined boundary between "model produces a tool call" and "tool call is executed safely". All failures — unknown tool names, missing required arguments, type mismatches, and exceptions thrown inside the tool function — are captured as structured `ToolResult.err` values rather than propagated as unhandled exceptions. Every dispatch attempt is wrapped in an OpenTelemetry-compatible tracing span so that tool usage is visible in the observability pipeline.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `Tool` | dataclass | A callable tool definition. |
| `ToolCall` | dataclass | A model-requested invocation of a named tool. |
| `ToolResult` | frozen dataclass | Structured outcome of a tool dispatch. |
| `ToolRegistry` | class | Name-keyed store of registered tools. |
| `ToolDispatcher` | class | Validates arguments and executes tool calls safely. |

### `Tool`

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]   # JSON-Schema-subset
    fn: Any                      # Callable[..., Awaitable[Any]] | Callable[..., Any]
```

`parameters` follows a JSON Schema subset: `type`, `properties`, `required` at the top level.

### `ToolCall`

```python
@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str = ""
```

### `ToolResult`

```python
@dataclass(frozen=True)
class ToolResult:
    call_id: str
    name: str
    output: Any
    error: str | None = None
    success: bool = True
```

| Class method | Signature | Description |
|---|---|---|
| `ok` | `(call_id: str, name: str, output: Any) -> ToolResult` | Convenience constructor for a successful result. |
| `err` | `(call_id: str, name: str, error: str) -> ToolResult` | Convenience constructor for an error result. |

### `ToolRegistry`

```python
ToolRegistry()
```

| Method | Signature | Description |
|---|---|---|
| `register` | `(tool: Tool) -> None` | Register a tool; overwrites any existing tool with the same name. |
| `get` | `(name: str) -> Tool \| None` | Look up a tool by name. |
| `names` | `() -> list[str]` | Return all registered tool names in alphabetical order. |
| `all_tools` | `() -> list[Tool]` | Return all registered tools in alphabetical name order. |

### `ToolDispatcher`

```python
ToolDispatcher(registry: ToolRegistry)
```

| Method | Signature | Description |
|---|---|---|
| `dispatch` | `async (call: ToolCall) -> ToolResult` | Execute the call; always returns a `ToolResult`, never raises. |

---

## Architecture

### Conceptual view

```
  LLM model output
        |
   ToolCall(name, arguments, call_id)
        |
  ToolDispatcher.dispatch()
        |
   +----+-------------------------------+
   |                                   |
 [1] ToolRegistry.get(name)        [span emitted]
   |                                   |
 [2] _validate_arguments(tool, args)
   |
 [3] tool.fn(**arguments)
       |              |
   (async fn)    (sync fn via asyncio.to_thread)
       |
 ToolResult.ok / ToolResult.err
        |
  caller receives structured result
```

### Data flow

1. The agent runtime receives a model response containing one or more tool calls.
2. For each tool call, the runtime constructs a `ToolCall` with the model-provided `name`, `arguments` dict, and correlation `call_id`.
3. `ToolDispatcher.dispatch(call)` opens a `SpanKind.TOOL` tracing span named `tool:<name>`.
4. The dispatcher looks up the tool in `ToolRegistry`. If the name is unknown, it immediately returns `ToolResult.err` with a descriptive message and marks the span `ERROR`.
5. `_validate_arguments` checks that all `required` keys are present and that values match the declared `type`. On failure, returns `ToolResult.err`.
6. The dispatcher checks whether `tool.fn` is a coroutine function (`inspect.iscoroutinefunction`). If yes, it awaits it directly. If no, it runs it in a thread pool via `asyncio.to_thread` to avoid blocking the event loop.
7. Any exception raised inside `tool.fn` is caught, formatted as `"ExcType: message"`, and returned as `ToolResult.err`.
8. On success, `ToolResult.ok` is returned and the span is marked `OK`.

### Key abstractions

**`Tool`** — a static descriptor plus an executable. The `parameters` field serves dual purpose: it is used by the dispatcher for validation and can be serialized to the model as the tool's function-calling schema. The `fn` field holds the actual callable, which may be sync or async.

**`ToolCall`** — the message from the model to the system. The `call_id` echoes back to the model in the result for correlation when multiple tools are called in a single turn. An empty `call_id` is valid for single-tool or test scenarios.

**`ToolResult`** — a frozen, value-type result. The `frozen=True` dataclass means results are hashable and safe to cache. The `ok` and `err` class methods enforce the invariant that `success=True` iff `error=None` and `output` is set.

**`ToolRegistry`** — a simple name-to-`Tool` dict with alphabetical ordering on reads. Duplicate registration silently overwrites, which allows hot-reloading or patching tools without clearing the registry.

**`ToolDispatcher`** — the execution boundary. It is the only component that calls user-provided `fn` callables. By wrapping all calls in try/except and emitting tracing spans, it provides a uniform safety and observability layer regardless of what the tool does internally.

---

## Design decisions and tradeoffs

- **Decision**: Validation uses only a JSON-Schema subset (required keys and top-level type checking). **Why**: Full JSON Schema validation (patterns, min/max, nested objects) requires a dependency like `jsonschema`. A subset covers the vast majority of LLM tool-calling contracts while keeping the module dependency-free. **Tradeoff**: Schemas with nested object types, enums, or constraints are not validated beyond top-level type presence. Invalid nested values pass validation silently.

- **Decision**: Sync callables are run via `asyncio.to_thread`. **Why**: Many existing utility functions (file I/O, HTTP with `requests`, database calls with sync drivers) are sync. Blocking the event loop with a sync call would stall all other coroutines. `to_thread` allows reuse of sync functions without requiring callers to rewrite them. **Tradeoff**: `to_thread` submits work to the default `ThreadPoolExecutor`, which has a finite thread pool. Under very high concurrency, sync tools can cause thread pool exhaustion. Async tools do not have this issue.

- **Decision**: Duplicate registration in `ToolRegistry` silently overwrites. **Why**: Allows tools to be patched or upgraded without explicitly deregistering the old version. **Tradeoff**: Accidental name collisions between independently registered tools go undetected. Production registries should enforce uniqueness explicitly.

- **Decision**: `ToolResult` is frozen (`frozen=True`). **Why**: Results are facts about what happened. Making them immutable prevents callers from accidentally modifying a result after the fact, which would corrupt tracing or audit logs. **Tradeoff**: Results cannot be cheaply modified (e.g. to add metadata); callers must construct a new result.

- **Decision**: Every dispatch emits a `SpanKind.TOOL` tracing span unconditionally. **Why**: Tool calls are a primary cost and failure mode in agent systems. Unconditional instrumentation ensures that observability coverage does not degrade as new tools are added. **Tradeoff**: Extremely high-frequency micro-tools (e.g. a tool called thousands of times per second) will produce proportionally large trace data volumes.

---

## Scaling concerns

- `ToolRegistry` is an in-memory dict. Lookup is O(1). It is not designed for multi-process or distributed scenarios — each process maintains its own registry.
- `ToolDispatcher.dispatch` is non-blocking for async tools. For sync tools, concurrency is bounded by the `ThreadPoolExecutor` thread count (default: `min(32, os.cpu_count() + 4)`). Under high load, sync tools queue behind each other.
- `_validate_arguments` iterates over the arguments dict and the schema properties. Both are small (typically fewer than 20 keys) so validation is effectively O(1) per call.
- There is no rate limiting or concurrency cap on how many tool calls can be in flight simultaneously. If the agent issues many parallel tool calls, all of them enter the thread pool at once.
- No caching of tool results is implemented. Idempotent tools that are called repeatedly with the same arguments perform full re-execution each time.

---

## Future improvements

- **Full JSON Schema validation**: Add optional support for a `jsonschema`-backed validator that handles nested objects, enum constraints, min/max, and string patterns. Keep the current subset validator as the default for zero-dependency environments.
- **Tool result caching**: Add an optional `cache: bool` flag to `Tool` and maintain a per-dispatcher result cache keyed by `(name, frozen_arguments)` for idempotent tools.
- **Concurrency cap for sync tools**: Add a `max_concurrent_sync: int` parameter to `ToolDispatcher` that limits how many sync tools run concurrently in the thread pool, preventing thread exhaustion under load.
- **Tool versioning**: Add a `version: str` field to `Tool` and surface it in trace spans so that tool upgrades are visible in the observability pipeline.
- **Batch dispatch**: Add a `dispatch_all(calls: list[ToolCall]) -> list[ToolResult]` method that runs all async calls concurrently and all sync calls in bounded thread batches.

---

## Usage examples

**Registering and dispatching a simple async tool:**

```python
import asyncio
from llm_agents.core.tool_orchestration import Tool, ToolCall, ToolRegistry, ToolDispatcher

async def add(a: int, b: int) -> int:
    return a + b

registry = ToolRegistry()
registry.register(Tool(
    name="add",
    description="Add two integers and return the sum.",
    parameters={
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    },
    fn=add,
))

dispatcher = ToolDispatcher(registry)
call = ToolCall(name="add", arguments={"a": 3, "b": 7}, call_id="call-001")
result = asyncio.run(dispatcher.dispatch(call))
assert result.success
assert result.output == 10
```

**Handling an unknown tool gracefully:**

```python
call = ToolCall(name="nonexistent", arguments={}, call_id="call-002")
result = asyncio.run(dispatcher.dispatch(call))
assert not result.success
assert "Unknown tool" in result.error
```

**Listing all registered tools for model function-calling schema:**

```python
schema = [
    {"name": t.name, "description": t.description, "parameters": t.parameters}
    for t in registry.all_tools()
]
# Pass `schema` to the model's tools parameter
```
