# evaluation/benchmarking

## Overview

The `evaluation/benchmarking` module provides infrastructure for running structured agent benchmarks: named task suites containing individual benchmark tasks, an async runner that executes an agent callable over every task and records rich per-task telemetry (latency, token counts, cost, cache hits), and a report structure with aggregated statistics including 95th-percentile latency. The module exists to support systematic, repeatable quality and efficiency measurement across different model configurations and agent versions. Where the `evaluation/framework` module focuses on generic metric-based scoring with repeat runs, benchmarking focuses on structured suites with operational metrics (cost, token usage, cache efficiency) that matter when selecting a model for production deployment. A built-in CLI entrypoint (`python -m llm_agents.evaluation.benchmarking`) allows running benchmark suites without writing Python code.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `BenchmarkTask` | dataclass | A single task with a unique ID, input, and expected output. |
| `Suite` | dataclass | Named ordered collection of `BenchmarkTask` objects; includes `from_jsonl` class method. |
| `TaskResult` | dataclass | Execution outcome for one task, including tokens, cost, latency, and cache hit. |
| `BenchmarkReport` | dataclass | Aggregated statistics for a completed suite run. |
| `BenchmarkRunner` | class | Async runner that executes a `Suite` and produces a `BenchmarkReport`. |
| `BUILTIN_SUITES` | dict | Five ready-to-run `Suite` objects keyed by name. |
| `BUILTIN_AGENTS` | dict | Paired async agent callables for each built-in suite. |

### BenchmarkTask

```
BenchmarkTask(
    task_id: str,
    input: str,
    expected_output: str,
    metadata: dict[str, Any] = {},
)
```

### Suite

```
Suite(
    name: str,
    tasks: list[BenchmarkTask] = [],
)
```

### TaskResult

```
TaskResult(
    task_id: str,
    success: bool,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_s: float = 0.0,
    cost_usd: float = 0.0,
    cache_hit: bool = False,
    actual_output: str = "",
    error: str | None = None,
)
```

### BenchmarkReport

```
BenchmarkReport(
    suite_name: str,
    task_results: list[TaskResult] = [],
    success_rate: float = 0.0,
    mean_tokens: float = 0.0,
    mean_latency_s: float = 0.0,
    p95_latency_s: float = 0.0,
    mean_cost_usd: float = 0.0,
    cache_hit_rate: float = 0.0,
)
```

### BenchmarkRunner

```
BenchmarkRunner(
    agent_fn: Callable[[str], Coroutine[Any, Any, Any]],
    scorer: Callable[[str, str], bool] | None = None,
)

async run(suite: Suite) -> BenchmarkReport
```

`agent_fn` may return a plain `str` or any object with `.output`, `.prompt_tokens`, `.completion_tokens`, `.cost_usd`, and `.cache_hit` attributes. `scorer` defaults to exact string equality. Returns a `BenchmarkReport` with one `TaskResult` per task.

### Suite.from_jsonl

```
Suite.from_jsonl(
    path: str | Path,
    *,
    name: str | None = None,
) -> Suite
```

Loads a `Suite` from a JSONL file. Each line must be a JSON object with `task_id`, `input`, and `expected_output` keys. An optional `metadata` dict key is preserved. Blank lines are silently skipped. The suite name defaults to the file stem if `name` is not provided.

### Built-in suites and agents

```python
from llm_agents.evaluation.benchmarking import BUILTIN_SUITES, BUILTIN_AGENTS
```

`BUILTIN_SUITES` maps suite name to `Suite` instance. `BUILTIN_AGENTS` maps the same name to the paired async agent callable. All five built-in suites produce 100 % success rate when run against their paired agent.

| Suite key | Tasks | Agent type | What it exercises |
|---|---|---|---|
| `tiny` | 3 | dict lookup | Harness smoke test |
| `arithmetic` | 50 | Python `eval` | Arithmetic expression evaluation |
| `qa_lookup` | 30 | dict lookup | Factual knowledge retrieval |
| `hallucination` | 25 | `OverlapDetector` | Passage/claim grounding verification |
| `classification` | 20 | keyword counting | Sentiment classification |

---

## Architecture

### Conceptual view

```
           Suite
        (list of BenchmarkTask)
               |
               v
        BenchmarkRunner
        /              \
   agent_fn           scorer
   (async)         (str, str) -> bool
        \              /
         TaskResult list
               |
               v
         _build_report()
               |
               v
         BenchmarkReport
         (aggregated stats)
```

### Data flow

1. The caller constructs a `Suite` with a name and a list of `BenchmarkTask` objects.
2. `BenchmarkRunner.run(suite)` iterates over `suite.tasks` sequentially.
3. For each task, `_run_task` is called:
   a. `time.perf_counter()` records the start time.
   b. `agent_fn(task.input)` is awaited. The return value is introspected: if it is a `str`, it is used as the output directly; otherwise `getattr` with defaults extracts `.output`, `.prompt_tokens`, `.completion_tokens`, `.cost_usd`, and `.cache_hit`.
   c. If an exception occurs, it is captured in `error` and `success` is forced to `False`.
   d. Otherwise `success = scorer(task.expected_output, output_str)`.
   e. Latency is computed as the elapsed time since the start.
   f. A `TaskResult` is built and appended to the results list.
4. After all tasks complete, `_build_report(suite_name, results)` computes:
   - `success_rate`: fraction of tasks where `success=True`.
   - `mean_tokens`: mean of `(prompt_tokens + completion_tokens)` per task.
   - `mean_latency_s`: arithmetic mean of per-task latencies.
   - `p95_latency_s`: 95th-percentile latency using the nearest-rank method. Returns `0.0` for empty input.
   - `mean_cost_usd`: mean cost per task.
   - `cache_hit_rate`: fraction of tasks with `cache_hit=True`.
5. The `BenchmarkReport` is returned to the caller.

### Key abstractions

**BenchmarkTask** extends the evaluation framework's `EvalCase` concept by adding `task_id` as a first-class required field rather than an optional default-empty string. This enforces traceability: every task in a benchmark suite must be identifiable.

**Suite** is a container that gives a set of tasks a name. The name is echoed in `BenchmarkReport.suite_name`, enabling downstream systems (dashboards, CI pipelines) to correlate reports with the suite that produced them.

**TaskResult** records operational metrics alongside correctness. Token counts and cost are optional (`0` when unavailable) because not all agent implementations expose them. The `cache_hit` flag supports analysis of how caching strategies affect benchmark performance.

**Scorer vs Metric**: the runner uses a `Callable[[str, str], bool]` scorer (boolean pass/fail) rather than the framework's float-returning `Metric` protocol. This reflects a benchmarking philosophy where tasks are either solved or not, rather than scored on a continuous scale. Callers who need graduated scores should use the `evaluation/framework` module directly.

**AgentOutput duck typing**: the runner reads attributes with `getattr(..., default)` rather than requiring a specific class. This makes the runner compatible with any structured output type that carries the expected fields, without requiring a formal protocol import.

---

## Design decisions and tradeoffs

- **Decision**: p95 latency uses the nearest-rank method and returns `0.0` for fewer than 20 tasks (by convention, though the computation itself works for any size). **Why**: p95 is statistically meaningful only with sufficient samples. The `0.0` sentinel flags the value as unreliable rather than misleading the caller. **Tradeoff**: The implementation actually computes nearest-rank for any list size; the docstring says "0.0 if fewer than 20 tasks" but the code does not enforce that cutoff — it returns `0.0` only for an empty list.

- **Decision**: The runner uses duck typing (`getattr` with defaults) for agent outputs rather than a formal `AgentOutput` Protocol. **Why**: Avoids requiring agent implementations to import and register with an additional interface. Many existing wrappers around OpenAI, HuggingFace, or vLLM already expose these attributes naturally. **Tradeoff**: Type errors (e.g., wrong attribute type) surface at runtime rather than being caught statically.

- **Decision**: Suite tasks are run sequentially, not concurrently. **Why**: Sequential execution provides reproducible latency measurements unaffected by concurrent load on shared resources. Concurrent runs would produce latencies that reflect resource contention rather than agent performance. **Tradeoff**: Large suites run slowly; elapsed wall time is proportional to the number of tasks.

- **Decision**: The CLI entrypoint (`__main__.py`) uses a stub agent that echoes expected answers. **Why**: Enables a fully self-contained smoke test of the benchmarking pipeline without requiring a real LLM or network access. **Tradeoff**: The built-in `tiny` suite does not test real agent behavior and should not be mistaken for a quality metric.

---

## Scaling concerns

Like the evaluation harness, the runner is sequential. For large suites (hundreds to thousands of tasks), wall-clock runtime is the primary constraint. Each task incurs the full latency of one `agent_fn` call. The `_build_report` aggregation is O(n log n) due to the sort inside `_percentile`, which is negligible compared to agent call latency. Memory usage is proportional to the number of tasks (one `TaskResult` per task). Token-count and cost fields are stored as plain floats and integers, keeping per-result memory minimal.

**What breaks first**: wall-clock runtime. A 1000-task suite at 500 ms per task takes over 8 minutes.

**Ceiling**: practical limit for interactive use is ~200 tasks. CI pipelines can handle larger suites with appropriate timeout budgets.

---

## Future improvements

- **Concurrent task execution**: add a `concurrency` parameter to `BenchmarkRunner.run` that uses `asyncio.Semaphore` to cap simultaneous agent calls, allowing throughput to scale with available API rate limit.
- **Percentile threshold enforcement**: enforce the "fewer than 20 tasks" precondition in `_build_report` and store a `p95_valid: bool` flag in `BenchmarkReport` rather than relying on callers to remember the limitation.
- **File-system suite registry**: extend `__main__` to discover JSONL suite files from a configured directory, enabling external suite definitions without code changes.
- **Incremental reporting**: emit intermediate `BenchmarkReport` snapshots as tasks complete, enabling progress monitoring for long-running suite runs.
- **LLM-backed agent suites**: add suites that wire real LLM backends (`OpenAIBackend`, `LlamaCppBackend`) to measure actual groundedness, hallucination rate, F1, and cost metrics across deployment profiles.

---

## Usage examples

Running a custom suite against an agent:

```python
import asyncio
from llm_agents.evaluation.benchmarking import BenchmarkTask, Suite, BenchmarkRunner

tasks = [
    BenchmarkTask(task_id="t1", input="2+2", expected_output="4"),
    BenchmarkTask(task_id="t2", input="3*3", expected_output="9"),
]
suite = Suite(name="arithmetic", tasks=tasks)

async def my_agent(input_text: str) -> str:
    return eval(input_text)  # stub; replace with real agent

runner = BenchmarkRunner(agent_fn=my_agent)
report = asyncio.run(runner.run(suite))
print(f"success_rate={report.success_rate}, p95_latency={report.p95_latency_s:.3f}s")
```

Custom scorer (case-insensitive):

```python
runner = BenchmarkRunner(
    agent_fn=my_agent,
    scorer=lambda expected, actual: actual.strip().lower() == expected.strip().lower(),
)
report = asyncio.run(runner.run(suite))
```

Using a built-in suite with its paired agent:

```python
import asyncio
from llm_agents.evaluation.benchmarking import (
    BUILTIN_AGENTS, BUILTIN_SUITES, BenchmarkRunner,
)

suite = BUILTIN_SUITES["arithmetic"]          # 50 arithmetic tasks
agent = BUILTIN_AGENTS["arithmetic"]          # Python eval agent
runner = BenchmarkRunner(agent_fn=agent)
report = asyncio.run(runner.run(suite))
print(f"success_rate={report.success_rate:.3f}")     # 1.000
print(f"p95_latency={report.p95_latency_s*1e6:.1f}µs")
```

Loading a suite from a JSONL file:

```python
from llm_agents.evaluation.benchmarking import Suite

suite = Suite.from_jsonl("/data/my_tasks.jsonl", name="my-benchmark")
print(f"Loaded {len(suite.tasks)} tasks from {suite.name}")
```

CLI usage:

```bash
# Single suite
python -m llm_agents.evaluation.benchmarking --suite arithmetic

# All five built-in suites (JSON array)
python -m llm_agents.evaluation.benchmarking --suite all
```

Inspecting per-task results:

```python
for task_result in report.task_results:
    status = "PASS" if task_result.success else "FAIL"
    print(f"{task_result.task_id}: {status}, latency={task_result.latency_s:.3f}s")
```
