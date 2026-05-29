# hierarchical_agents

## Overview

The `hierarchical_agents` module implements a supervisor/worker pattern for multi-agent orchestration. A `Supervisor` decomposes a high-level goal into subtasks using a `Planner`, then delegates each subtask to one or more `Worker` agents drawn from a pool. Workers execute their assigned task by calling an LLM router or dispatching a named tool, and return structured `AgentResult` objects. The supervisor aggregates all results into a `SupervisorResult`. The module exists to give the system a clear separation between coordination (goal decomposition, worker assignment, result aggregation) and execution (single-task completion), enabling multi-agent workflows to be composed from interchangeable worker implementations. Execution can be sequential (for debugging and determinism) or parallel (for latency reduction on independent subtasks).

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `AgentResult` | dataclass | Outcome of a single agent task invocation. |
| `SupervisorResult` | dataclass | Aggregated outcomes of all delegated subtasks. |
| `Agent` | Protocol | Interface for any agent implementation. |
| `Worker` | class | Concrete agent that answers tasks via LLM or tool calls. |
| `Supervisor` | class | Coordinates a pool of workers to achieve a goal. |

### `AgentResult`

```python
@dataclass
class AgentResult:
    task: str
    output: Any
    success: bool = True
    error: str | None = None
```

| Class method | Signature | Description |
|---|---|---|
| `ok` | `(task: str, output: Any) -> AgentResult` | Convenience constructor for a successful result. |
| `err` | `(task: str, error: str) -> AgentResult` | Convenience constructor for a failed result. |

### `SupervisorResult`

```python
@dataclass
class SupervisorResult:
    goal: str
    results: list[AgentResult] = field(default_factory=list)
    success: bool = True
    failed_count: int = 0
```

### `Agent` (Protocol)

```python
@runtime_checkable
class Agent(Protocol):
    async def run(self, task: str) -> AgentResult: ...
```

Any object with a matching `run(task) -> AgentResult` coroutine satisfies this interface.

### `Worker`

```python
Worker(
    router: Any,
    model: str = "default",
    dispatcher: ToolDispatcher | None = None,
    tool_name: str | None = None,
)
```

| Method | Signature | Description |
|---|---|---|
| `run` | `async (task: str) -> AgentResult` | Execute task via LLM or tool; always returns `AgentResult`, never raises. |

When `tool_name` is set and `dispatcher` is provided, `Worker` dispatches a `ToolCall` with `arguments={"query": task}` instead of calling the router.

### `Supervisor`

```python
Supervisor(
    planner: Planner,
    workers: list[Any],
    *,
    parallel: bool = False,
)
```

Raises `ValueError` if `workers` is empty.

| Method | Signature | Description |
|---|---|---|
| `run` | `async (goal: str) -> SupervisorResult` | Decompose goal, delegate to workers, aggregate results. |

---

## Architecture

### Conceptual view

```
           goal string
                |
          Supervisor.run()
                |
          Planner.plan(goal)
                |
              Plan
           [Step, Step, ...]
                |
    round-robin worker assignment
                |
       +---------+---------+
       |         |         |
   Worker[0]  Worker[1]  Worker[0]  ...
       |         |         |
  LLM call   Tool call   LLM call
       |         |         |
  AgentResult AgentResult AgentResult
       |
   SupervisorResult
   (goal, results[], success, failed_count)
```

Workers are selected by `index % len(workers)`, so in a pool of two workers, steps 0, 2, 4... go to `workers[0]` and steps 1, 3, 5... go to `workers[1]`.

### Data flow

**Sequential mode (default):**

1. `Supervisor.run(goal)` opens a `SpanKind.AGENT` tracing span named `"supervisor:run"`.
2. The planner is called: `plan = await self._planner.plan(goal)`.
3. `_delegate_sequential` iterates steps in order. For each step `i`, worker `i % len(workers)` is called with `worker.run(step.description)`.
4. `AgentResult` objects are collected in order.
5. Failures are counted. `SupervisorResult.success = (failed_count == 0)`.
6. The span is marked `OK` or `ERROR` depending on whether any tasks failed.

**Parallel mode (`parallel=True`):**

1. Steps 1-2 are identical.
2. `_delegate_parallel` builds a list of coroutines `worker.run(step.description)` for all steps simultaneously.
3. `asyncio.gather(*tasks, return_exceptions=True)` dispatches all coroutines concurrently.
4. Each result is checked: if it is a `BaseException` (raised by `gather` when `return_exceptions=True`), it is converted to `AgentResult.err`.
5. Results are collected in the same order as the steps.
6. Failure counting and result aggregation proceed as in sequential mode.

**Worker execution:**

1. If `tool_name` is set and `dispatcher` is provided, `Worker._run_tool` constructs a `ToolCall(name=tool_name, arguments={"query": task})` and dispatches it.
2. Otherwise, `Worker._run_llm` constructs an `LLMRequest(model=model, messages=[{role: "user", content: task}])` and calls `router.complete`.
3. Any exception is caught and returned as `AgentResult.err`.

### Key abstractions

**`Agent` (Protocol)** — the minimal interface for any component that can execute a task. A `Worker` satisfies it, but so does any test double, specialized sub-agent, or third-party component with a compatible `run` method. The `@runtime_checkable` decorator supports `isinstance(obj, Agent)` checks in tests.

**`Worker`** — the atomic execution unit. Its dual mode (LLM or tool) means the same pool can contain workers specialized for different subtask types (e.g. one worker for web search via tool, another for synthesis via LLM) without the supervisor needing to know which mode each worker uses.

**`Supervisor`** — the orchestration layer. It does not know how workers are implemented; it only knows that they satisfy the `Agent` protocol. The `parallel` flag is a construction-time decision rather than a per-run decision, which simplifies reasoning about concurrency.

**`SupervisorResult`** — the aggregated view of a run. It preserves all `AgentResult` objects in step order so the caller can inspect partial success, retry failed tasks, or extract results by position.

---

## Design decisions and tradeoffs

- **Decision**: Round-robin worker assignment. **Why**: Simple, fair, and deterministic. Workers in the pool are assumed to be homogeneous (same capability, same model). Round-robin distributes load evenly without requiring load sensing. **Tradeoff**: Workers with different capabilities cannot be assigned by task type. A more sophisticated assignment strategy would require task classification and worker capability tagging.

- **Decision**: Worker failures are recorded but do not abort remaining delegations. **Why**: In multi-step workflows, a failure in step 3 should not prevent steps 4 and 5 from running, especially when they are independent. The supervisor aggregates all results and the caller decides how to handle failures. **Tradeoff**: A failed step may produce downstream failures if later steps depend on its output, but the supervisor has no dependency model to detect this.

- **Decision**: `parallel=False` by default. **Why**: Sequential execution is deterministic, easier to trace, and avoids concurrency bugs during development. Parallel mode is an opt-in performance optimization. **Tradeoff**: Sequential execution is slow for goals decomposed into many independent subtasks, especially when each step involves a network call.

- **Decision**: Tool-mode `Worker` passes the entire task string as `arguments={"query": task}`. **Why**: The task string is natural language, so the only sensible argument is the full description. This avoids a secondary parsing step to extract structured arguments from the task. **Tradeoff**: Tools that require structured arguments (e.g. `{"city": "Berlin", "date": "2026-05-29"}`) cannot be used directly from a `Worker`; the caller must use `ToolDispatcher` directly or write a custom `Agent` implementation.

- **Decision**: `Supervisor` validates that `workers` is non-empty at construction time. **Why**: An empty worker pool would cause a `ZeroDivisionError` at delegation time from the modulo operation. Failing early with a clear `ValueError` is safer. **Tradeoff**: None. This is strictly better than a late error.

---

## Scaling concerns

- Sequential execution throughput is bounded by the latency of the slowest step. For a 10-step plan with each step taking 2 seconds, total execution time is at least 20 seconds.
- Parallel execution with `asyncio.gather` runs all steps concurrently. For a pool of N workers and K steps, effective concurrency is min(K, event loop capacity). Rate limits on the LLM provider become the primary bottleneck.
- The `_delegate_parallel` implementation passes `return_exceptions=True` to `gather`, so exceptions in individual workers are captured rather than propagating. However, if a worker is a sync function that blocks the event loop, it will stall all parallel coroutines.
- `SupervisorResult.results` stores all `AgentResult` objects in memory. For very long-running supervisors with thousands of steps, this list grows proportionally. There is no streaming or incremental consumption.
- `Planner.plan` is called once per `Supervisor.run` invocation. For goals that change frequently, the planner call is a fixed overhead. There is no plan caching.

---

## Future improvements

- **Capability-based worker routing**: Add a `capabilities: set[str]` field to `Worker` and a corresponding `requires: str | None` to `Step`, then assign workers by capability match rather than round-robin.
- **Streaming results**: Add an async generator variant of `Supervisor.run` that yields `AgentResult` objects as steps complete, rather than waiting for all steps to finish before returning `SupervisorResult`.
- **Dependency-aware parallel execution**: Add a `dependencies: list[str]` field to `Step` (step IDs) and execute steps as soon as their dependencies are satisfied, rather than fully sequential or fully parallel.
- **Retry policy per worker**: Allow each `Worker` to have a configurable retry count for transient errors (rate limits, network timeouts) before returning `AgentResult.err`.
- **Heterogeneous worker pools**: Allow the supervisor to accept different worker types for different step categories, with a dispatcher function that selects the right worker based on step metadata.

---

## Usage examples

**Basic supervisor with a single worker:**

```python
from llm_agents.core.hierarchical_agents import Worker, Supervisor
from llm_agents.core.planning import LLMPlanner

worker = Worker(router=router, model="gpt-4o-mini")
planner = LLMPlanner(router=router, model="gpt-4o")
supervisor = Supervisor(planner=planner, workers=[worker])

result = await supervisor.run("Research the top 3 Python web frameworks and compare them.")

print(f"Goal: {result.goal}")
print(f"Success: {result.success}, Failed: {result.failed_count}")
for agent_result in result.results:
    print(f"  Task: {agent_result.task}")
    print(f"  Output: {agent_result.output[:100] if agent_result.output else agent_result.error}")
```

**Parallel execution with multiple workers:**

```python
from llm_agents.core.hierarchical_agents import Worker, Supervisor
from llm_agents.core.planning import LLMPlanner

workers = [
    Worker(router=router, model="gpt-4o-mini"),
    Worker(router=router, model="gpt-4o-mini"),
    Worker(router=router, model="gpt-4o-mini"),
]
planner = LLMPlanner(router=router, model="gpt-4o")
supervisor = Supervisor(planner=planner, workers=workers, parallel=True)

result = await supervisor.run("Translate the product description into French, German, and Spanish.")
```

**Tool-backed worker for specialized tasks:**

```python
from llm_agents.core.hierarchical_agents import Worker, Supervisor
from llm_agents.core.tool_orchestration import ToolRegistry, ToolDispatcher, Tool

registry = ToolRegistry()
registry.register(Tool(
    name="web_search",
    description="Search the web and return top results.",
    parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    fn=my_search_function,
))
dispatcher = ToolDispatcher(registry)

search_worker = Worker(router=router, model="gpt-4o", dispatcher=dispatcher, tool_name="web_search")
synthesis_worker = Worker(router=router, model="gpt-4o")

supervisor = Supervisor(planner=planner, workers=[search_worker, synthesis_worker])
result = await supervisor.run("Find recent news about Python 3.14 and write a summary.")
```
