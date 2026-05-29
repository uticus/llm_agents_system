# tracing

Module path: `src/llm_agents/infra/tracing/`

## Overview

The tracing module provides lightweight, OpenTelemetry-aligned distributed tracing for agent, tool, and LLM calls. It captures structured spans — named, timed, attributed units of work — assembles them into traces by a shared `trace_id`, and delivers finished spans to a pluggable collector. The module was built to give every operation in the agent pipeline a precise causal record without requiring an external tracing daemon at development time, while still exposing an export hook that can forward spans to production systems (Jaeger, Zipkin, OTLP). Context propagation relies on `contextvars` so that async coroutines running concurrently on the same thread each maintain their own span stack, which is the correct model for asyncio-based agents.

---

## Public API

Import everything from `llm_agents.infra.tracing`. Do not import from private submodules.

### Exported symbols

| Symbol | Kind | Description |
|---|---|---|
| `SpanStatus` | StrEnum | Terminal status of a finished span: `OK`, `ERROR`, `UNSET`. |
| `SpanKind` | StrEnum | Semantic category aligned with OpenTelemetry: `INTERNAL`, `LLM`, `TOOL`, `AGENT`. |
| `Span` | dataclass | Mutable live span open during a traced block. |
| `FinishedSpan` | frozen dataclass | Immutable snapshot written to the collector when the span closes. |
| `Trace` | frozen dataclass | All `FinishedSpan` objects sharing a `trace_id`, ordered by `start_time`. |
| `current_span` | function | Return the innermost active `Span` in the current async context, or `None`. |
| `Tracer` | class | Creates spans via context manager and decorator factory. |
| `tracer` | `Tracer` instance | Module-level singleton — use instead of instantiating `Tracer`. |
| `traced` | callable | Module-level alias for `tracer.traced` — decorator factory. |
| `InMemoryCollector` | class | Accumulates `FinishedSpan` objects; assembles `Trace` views. |
| `get_collector` | function | Return the shared `InMemoryCollector` singleton. |
| `serialize_trace` | function | Convert a `Trace` to a JSON-serializable `dict`. |
| `deserialize_trace` | function | Reconstruct a `Trace` from a previously serialized `dict`. |
| `SCHEMA_VERSION` | `int` | Current serialization schema version (1). |

### `Tracer`

```
class Tracer
```

**Method: `span`**
```
def span(
    self,
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    **attrs: Any,
) -> _SpanContext
```
Returns a dual-protocol context manager (supports both `with` and `async with`). Opens a new span linked to the current span as parent (if one exists). `attrs` are stored as span attributes.

**Method: `traced`**
```
def traced(
    self,
    name: str | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
    **attrs: Any,
) -> Callable
```
Decorator factory. Wraps sync or async functions in a span. The span name defaults to `fn.__qualname__` when `name` is `None`.

### `InMemoryCollector`

```
class InMemoryCollector
```

| Method | Signature | Description |
|---|---|---|
| `add` | `(span: FinishedSpan) -> None` | Record a span and invoke the export hook. |
| `set_export_hook` | `(hook: Callable[[FinishedSpan], None] \| None) -> None` | Register or clear the export hook. |
| `reset` | `() -> None` | Clear all spans and the hook. Use in test teardown. |
| `get_trace` | `(trace_id: str) -> Trace \| None` | Return all spans for a trace, ordered by `start_time`. |
| `all_traces` | `() -> list[Trace]` | Return every recorded trace. |

### `Span` (dataclass fields)

| Field | Type | Description |
|---|---|---|
| `trace_id` | `str` | Hex UUID shared by all spans in one trace. |
| `span_id` | `str` | Hex UUID unique to this span. |
| `parent_id` | `str \| None` | Parent span id, or `None` for root spans. |
| `name` | `str` | Human-readable operation name. |
| `kind` | `SpanKind` | Semantic category. |
| `start_time` | `float` | `perf_counter()` value at open. |
| `start_wall` | `str` | ISO-8601 UTC datetime string at open. |
| `status` | `SpanStatus` | Mutable; defaults to `UNSET`, set to `OK`/`ERROR` on close. |
| `attributes` | `dict[str, Any]` | Mutable key/value bag for caller-attached metadata. |

`FinishedSpan` adds `end_time: float` and `duration_s: float` and is frozen.

### `serialize_trace` / `deserialize_trace`

```
def serialize_trace(trace: Trace) -> dict[str, Any]
def deserialize_trace(data: dict[str, Any]) -> Trace
```

`deserialize_trace` raises `ValueError` on missing required fields and emits a `UserWarning` on schema version mismatch (forward-compatible signal).

---

## Architecture

### Conceptual view

```
Caller code
    |
    | tracer.span(...) / @traced(...)
    v
_SpanContext (context manager)
    |-- on enter:  generate IDs, read current_span() -> parent link
    |              _set_span() -> push to ContextVar stack
    |-- on exit:   compute duration, set status, create FinishedSpan
    |              _reset_span() -> pop from ContextVar stack
    |              InMemoryCollector.add(finished_span)
    |                   |
    |                   +-- invoke export hook (e.g. bridge_span)
    v
InMemoryCollector._spans: list[FinishedSpan]
    |
    +-- get_trace(trace_id) -> Trace
    +-- all_traces()        -> list[Trace]
    |
    v (optional)
serialize_trace / deserialize_trace  ->  JSON dict  ->  disk / wire
```

### Data flow

1. The caller opens a span via `tracer.span("op", SpanKind.TOOL)` or applies `@traced(...)`.
2. `_SpanContext._open()` reads `current_span()` from the `ContextVar` to establish parent linkage. If no parent exists, a new `trace_id` is generated.
3. A `Span` object (mutable) is pushed into the `ContextVar`. Nested spans entered within the block see this span as their parent.
4. The caller attaches arbitrary attributes via `span.attributes["key"] = value`.
5. On block exit (normal or exception), `_SpanContext._close()` captures `end_time`, resolves the status to `OK` (normal) or `ERROR` (exception, with `attributes["error"]` set to the exception string), and constructs an immutable `FinishedSpan`.
6. The `FinishedSpan` is appended to `InMemoryCollector._spans`. The export hook (if set) is called synchronously. Hook exceptions are caught and forwarded to `warnings.warn` so they never interfere with traced code.
7. The previous span is restored in the `ContextVar` via the token returned by `_set_span`.

### Key abstractions

**`SpanKind` (StrEnum):** Models the semantic role of a span. Maps to OpenTelemetry span kinds so that tooling can distinguish LLM provider calls (`LLM`), memory or database reads (`TOOL`), agent orchestration (`AGENT`), and internal bookkeeping (`INTERNAL`). Using a StrEnum makes the value directly JSON-serializable without conversion.

**`Span` / `FinishedSpan` split:** `Span` is mutable because the caller needs to attach attributes while the block is running. `FinishedSpan` is a frozen dataclass because once a span is finished it must not change — the collector stores references, not copies. The split enforces the invariant at the type level.

**`ContextVar[Span | None]`:** A single `ContextVar` stores the active span per asyncio Task. `contextvars` copies are made automatically when new tasks are spawned, so nested agent calls running concurrently do not corrupt each other's trace trees. Thread-local storage is explicitly avoided because a single event-loop thread runs many coroutines simultaneously.

**`InMemoryCollector` singleton:** One process-global collector allows any code that imports `get_collector()` to access all spans without passing a collector reference through every call chain. The export hook slot allows production code to stream spans to an external system (OTLP exporter, logging sink) without changing the collector interface.

---

## Design decisions and tradeoffs

- **Decision:** Use `contextvars.ContextVar` for span propagation. **Why:** asyncio tasks inherit their parent's context snapshot, so parent–child relationships are correctly preserved across `await` boundaries and across `asyncio.create_task`. **Tradeoff:** Thread-based concurrency requires explicit context copying; the module documents that thread-local storage is forbidden for this use case.

- **Decision:** The `InMemoryCollector` export hook is synchronous. **Why:** Keeps the span close path simple and avoids the complexity of async hooks racing with the event loop. **Tradeoff:** A slow or blocking hook (e.g., a synchronous HTTP call to an OTLP endpoint) will delay the traced code path. Production hooks must be fast (e.g., enqueue to an in-process queue).

- **Decision:** `Span` and `FinishedSpan` are separate types. **Why:** Enforces the open/closed lifecycle at the type level. Callers that hold a `Span` know they can mutate attributes; callers that hold a `FinishedSpan` know the data is stable. **Tradeoff:** Slight duplication of field definitions across the two types.

- **Decision:** JSON serialization uses a versioned schema (`SCHEMA_VERSION = 1`). **Why:** Allows replay analysis tools to detect schema mismatches in stored traces without hard-failing. **Tradeoff:** Schema evolution requires backward-compatibility work in `deserialize_trace`; version mismatch is currently a warning, not an error.

- **Decision:** A module-level `tracer` singleton is provided. **Why:** Eliminates the need to instantiate and thread a `Tracer` object through every component. **Tradeoff:** Global mutable state makes unit testing slightly more complicated; tests must call `get_collector().reset()` in teardown.

---

## Scaling concerns

- **Memory:** `InMemoryCollector` stores every `FinishedSpan` in a Python list indefinitely. In a long-running process handling thousands of agent calls per hour, this list grows without bound. There is no eviction, compaction, or size limit. Memory growth is the primary scaling ceiling.

- **Export hook contention:** The hook is called synchronously on every span close. If many coroutines finish spans in quick succession (e.g., a large `asyncio.gather` batch), all hooks run sequentially in the event loop. A slow hook blocks all subsequent span closes.

- **`get_trace` linear scan:** `get_trace(trace_id)` iterates the entire `_spans` list. For a collector that holds millions of spans, this becomes O(n) per query.

- **No sampling:** Every span is recorded. There is no head-based or tail-based sampling mechanism. High-throughput production deployments will need to add a sampling layer before spans reach the collector.

- **No distributed propagation:** There is no W3C TraceContext header injection/extraction. Spans cannot be correlated across process boundaries without custom middleware.

---

## Future improvements

- **Bounded collector with eviction:** Add a `max_spans` parameter to `InMemoryCollector` with LRU or FIFO eviction to cap memory usage in long-running processes.

- **Async export hook:** Allow the hook to be a coroutine so that network-bound exporters (OTLP over HTTP) can run without blocking the event loop.

- **Indexed collector:** Maintain a `dict[str, list[FinishedSpan]]` index keyed on `trace_id` inside `InMemoryCollector` so that `get_trace` is O(1) rather than O(n).

- **W3C TraceContext propagation:** Add header injection/extraction helpers so that traces can be correlated across HTTP service boundaries.

- **Sampling API:** Add a `SamplerProtocol` that `_SpanContext._open()` consults before creating a span, enabling head-based sampling rates configurable per `SpanKind`.

- **OTLP exporter:** Provide a ready-made async OTLP/HTTP export hook that batches spans and ships them to Jaeger or a Tempo instance with configurable flush interval and queue size.

---

## Usage examples

### Context manager (sync)

```python
from llm_agents.infra.tracing import tracer, SpanKind, get_collector

with tracer.span("fetch_context", SpanKind.TOOL, source="postgres") as span:
    rows = db.query("SELECT * FROM docs WHERE topic = 'agents'")
    span.attributes["rows_returned"] = len(rows)

# Inspect the recorded trace
collector = get_collector()
traces = collector.all_traces()
print(traces[0].spans[0].duration_s)
```

### Context manager (async)

```python
from llm_agents.infra.tracing import tracer, SpanKind

async def call_model(prompt: str) -> str:
    async with tracer.span("llm_call", SpanKind.LLM, model="gpt-4o") as span:
        result = await openai_client.complete(prompt)
        span.attributes["tokens"] = result.usage.total_tokens
        return result.content
```

### Decorator factory

```python
from llm_agents.infra.tracing import traced, SpanKind

@traced("plan_step", SpanKind.AGENT, agent="planner")
async def run_planning_step(state: dict) -> dict:
    # entire function body is wrapped in a span automatically
    ...
    return updated_state
```

### Serialization round-trip

```python
import json
from llm_agents.infra.tracing import get_collector, serialize_trace, deserialize_trace

traces = get_collector().all_traces()
for trace in traces:
    blob = json.dumps(serialize_trace(trace))
    # store blob to disk or send over wire

    recovered = deserialize_trace(json.loads(blob))
    assert recovered.trace_id == trace.trace_id
```
