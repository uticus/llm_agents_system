# planning

## Overview

The `planning` module provides goal decomposition and step-by-step execution for LLM agents. It models a goal as a `Plan` consisting of an ordered list of `Step` objects, each of which is either answered by a direct LLM call or dispatched as a named tool call. The module provides two planner implementations — a trivial single-step planner and an LLM-driven decomposition planner — and an `execute` function that drives a plan to completion with built-in replanning on step failure. The module exists to separate the "what needs to be done" concern (planning) from the "how to do it" concern (tool dispatch, LLM calls), and to give agents a structured, observable execution path rather than a free-form generation loop.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `StepStatus` | StrEnum | Lifecycle state of a single step: `PENDING`, `RUNNING`, `DONE`, `FAILED`. |
| `PlanStatus` | StrEnum | Lifecycle state of a plan: `PENDING`, `RUNNING`, `DONE`, `FAILED`. |
| `Step` | dataclass | A single executable action within a plan. |
| `Plan` | dataclass | An ordered sequence of steps toward a goal. |
| `Planner` | Protocol | Interface for goal-to-plan strategies. |
| `SequentialPlanner` | class | Trivial planner that wraps the entire goal in one step. |
| `LLMPlanner` | class | Planner that calls an LLM to decompose the goal into `STEP:` lines. |
| `execute` | async function | Drive a plan to completion with replanning on failure. |

### `Step`

```python
@dataclass
class Step:
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None
```

### `Plan`

```python
@dataclass
class Plan:
    goal: str
    steps: list[Step]
    status: PlanStatus = PlanStatus.PENDING
```

### `Planner` (Protocol)

```python
@runtime_checkable
class Planner(Protocol):
    async def plan(self, goal: str, context: str = "") -> Plan: ...
```

### `SequentialPlanner`

```python
SequentialPlanner(model: str = "default")
```

| Method | Signature | Description |
|---|---|---|
| `plan` | `async (goal: str, context: str = "") -> Plan` | Returns a one-step plan; makes no LLM call. |

### `LLMPlanner`

```python
LLMPlanner(router: Any, model: str = "default")
```

| Method | Signature | Description |
|---|---|---|
| `plan` | `async (goal: str, context: str = "") -> Plan` | Calls the router once to parse `STEP:` lines; falls back to one step if none are found. |

### `execute`

```python
async def execute(
    plan: Plan,
    dispatcher: ToolDispatcher,
    router: Any,
    memory: ShortTermMemory | None = None,
    planner: Planner | None = None,
    max_replan: int = 1,
) -> Plan
```

Mutates `plan` in place and returns it. The `plan.status` and all `step.status` fields reflect final execution state. Emits a `SpanKind.AGENT` tracing span named `"plan:execute"`.

---

## Architecture

### Conceptual view

```
               goal string
                    |
         +----------+----------+
         |                     |
  SequentialPlanner        LLMPlanner
  (no LLM call)            (one LLM call
  one Step                  -> parse STEP: lines
                            -> N Steps, fallback to 1)
                    |
                  Plan
                    |
              execute()
                    |
          for each Step in order:
            |                 |
      tool_name set?       no tool_name
            |                 |
   ToolDispatcher.dispatch  router.complete
   (ToolCall from step)     (LLM call with memory context)
            |                 |
      step.result = output    step.result = response.content
      step.status = DONE      step.status = DONE
                    |
              failure path:
            planner.plan(step.description)
            -> new Steps replace failed step
            -> retry from same index
                    |
              Plan.status = DONE | FAILED
```

### Data flow

1. A caller provides a goal string to a planner.
2. The planner calls the router (for `LLMPlanner`) with a fixed `_DECOMPOSE_PROMPT` that instructs the model to produce `STEP: <description>` lines. `SequentialPlanner` skips this call entirely.
3. `LLMPlanner` parses the response with `_parse_steps`, which extracts lines beginning with `STEP:` (case-insensitive). Non-matching lines are ignored.
4. A `Plan` is returned with `status=PENDING`.
5. `execute` sets `plan.status = RUNNING` and iterates steps by index.
6. For each step:
   - If `step.tool_name` is set, a `ToolCall` is constructed from the step's `id`, `tool_name`, and `tool_arguments`, then dispatched via the `ToolDispatcher`. The result's `.output` is stored in `step.result`.
   - If `step.tool_name` is `None`, `execute` builds a prompt from optional memory context (`[role]: content` lines) plus `step.description`, then calls `router.complete`. The `response.content` is stored in `step.result`.
7. On step failure, if a `planner` is provided and `replan_budget > 0`, the failed step is replaced in `plan.steps` by calling `planner.plan(step.description)` and splicing in the resulting steps at the same index. The budget is decremented by one and execution retries from the same position.
8. If replanning is unavailable or the budget is exhausted, the plan halts with `PlanStatus.FAILED`.
9. On successful completion of all steps, `plan.status = DONE`.

### Key abstractions

**`Step`** — the unit of work. The `tool_name` field acts as a discriminated union tag: `None` means an LLM-answered step; non-`None` means a tool call. Auto-generated UUIDs for `id` ensure that each step is uniquely addressable in traces and logs without requiring the planner to manage identifiers.

**`Plan`** — a mutable container for execution state. The `steps` list is mutated during replanning (splice at index), so plans are not safe to share across concurrent `execute` calls.

**`Planner` (Protocol)** — the extension point. Any object with a matching `plan(goal, context) -> Plan` coroutine qualifies, including test stubs, planners backed by different models, and planners that use structured output formats rather than parsing `STEP:` lines.

**`SequentialPlanner`** — the zero-cost baseline. It produces a plan without making any LLM call, which is useful for unit tests, for goals that are already atomic, and as a fallback when the LLM planning call itself fails.

**`LLMPlanner`** — the primary implementation. The `_DECOMPOSE_PROMPT` format is intentionally prescriptive (`STEP: <text>`, one per line, nothing else) to make parsing robust. The fallback to a single-step plan means `execute` always receives at least one step, preventing empty-plan edge cases.

---

## Design decisions and tradeoffs

- **Decision**: Plans are mutated in place by `execute`. **Why**: Avoids creating a parallel state structure and makes the live execution state immediately visible to callers holding a reference to the plan (e.g. for progress monitoring). **Tradeoff**: Plans cannot be safely replayed or shared across concurrent executions. Callers that need immutable snapshots must deepcopy.

- **Decision**: Replanning replaces only the failed step, not the entire plan. **Why**: Minimizes disruption to successful steps already completed and avoids re-executing expensive operations. **Tradeoff**: The replacement steps generated by the planner may assume state from a blank start rather than from the partially completed plan, leading to context mismatch.

- **Decision**: `max_replan` defaults to `1`. **Why**: One replanning attempt catches transient tool errors (network timeout, rate limit) without risking infinite loops. **Tradeoff**: Complex goals where the first decomposition is systematically wrong will fail after one replan rather than converging through multiple attempts.

- **Decision**: Memory context is prepended to LLM step prompts as plain `[role]: content` lines. **Why**: Simple, format-agnostic, and works with any model without requiring a structured message history API. **Tradeoff**: The context format is not a standard conversation format. Models trained on chat-format data may not interpret the `[role]:` prefix as conversation context.

- **Decision**: `LLMPlanner` falls back to a single-step plan when no `STEP:` lines are found. **Why**: A silent fallback is safer than raising an exception, which would halt the entire agent. **Tradeoff**: If the model repeatedly fails to produce `STEP:` lines (due to a bad prompt or model mismatch), the fallback masks the problem and the agent executes a trivially wrong plan.

---

## Scaling concerns

- `execute` runs steps sequentially by design. For plans with independent steps (e.g. multiple parallel tool calls), this is inefficient. Parallelizing steps would require dependency tracking between steps.
- `LLMPlanner.plan` makes one LLM call per invocation. If called in a tight loop (e.g. for replanning on every failed step), the cost grows linearly with the number of replanning events.
- Plans with many steps (hundreds) will produce many sequential LLM calls or tool dispatches. There is no batching or pipelining.
- The replan splice operation on `plan.steps` is O(n) where n is the number of steps. This is negligible in practice but could become an issue for very large dynamically growing plans.
- Memory context injection uses `ShortTermMemory.items()` which returns all buffered items. For a large token budget with many items, the context injection string can itself be large.

---

## Future improvements

- **Parallel step execution**: Add a `dependencies` field to `Step` (list of step IDs that must complete first) and execute independent steps concurrently using `asyncio.gather`.
- **Structured planner output**: Add an `LLMPlannerJSON` variant that requests a JSON array of steps from the model and validates the schema, eliminating the brittle `STEP:` line parsing heuristic.
- **Plan checkpointing**: Serialize `Plan` state to a file or database after each step completes so that long-running plans can be resumed after process restart.
- **Conditional steps**: Add a `condition` field to `Step` that is evaluated against the previous step's result to support branching plans.
- **Plan cost estimation**: Before execution, estimate the total token cost and latency of a plan based on step count and tool types, and surface this to the caller.

---

## Usage examples

**Simple goal execution with `SequentialPlanner`:**

```python
from llm_agents.core.planning import SequentialPlanner, execute

planner = SequentialPlanner(model="gpt-4o-mini")
plan = await planner.plan("Summarize the latest quarterly report.")
completed_plan = await execute(plan, dispatcher=dispatcher, router=router)
print(completed_plan.steps[0].result)
```

**LLM-driven goal decomposition:**

```python
from llm_agents.core.planning import LLMPlanner, PlanStatus, execute

planner = LLMPlanner(router=router, model="gpt-4o")
plan = await planner.plan(
    goal="Research Python async patterns and write a blog post.",
    context="Target audience: intermediate Python developers.",
)

print(f"Plan has {len(plan.steps)} steps:")
for step in plan.steps:
    print(f"  - {step.description}")

result_plan = await execute(plan, dispatcher=dispatcher, router=router, max_replan=2)

if result_plan.status == PlanStatus.DONE:
    print("All steps completed successfully.")
else:
    print("Plan failed at:", next(s for s in result_plan.steps if s.error))
```

**Execution with memory context:**

```python
from llm_agents.core.planning import LLMPlanner, execute
from llm_agents.core.agent_memory import ShortTermMemory, MemoryItem
import time

memory = ShortTermMemory(token_budget=1024)
memory.add(MemoryItem(content="User is located in Berlin.", role="system", timestamp=time.monotonic()))

planner = LLMPlanner(router=router, model="gpt-4o")
plan = await planner.plan("Find the nearest Python meetup.")
await execute(plan, dispatcher=dispatcher, router=router, memory=memory)
```
