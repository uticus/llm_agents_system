# evaluation/framework

## Overview

The `evaluation/framework` module is the core evaluation engine for the llm_agents_system platform. It provides the foundational primitives needed to measure agent quality: a data model for test cases and results, a set of pluggable scoring metrics, an async execution harness that drives any agent function over a case set, and a statistical aggregation function that produces a structured report. The module exists because repeatable, metric-driven quality assessment is a prerequisite for safe iteration on agent prompts, architectures, and models. Without a shared harness all other evaluation submodules (prompts, benchmarking, hallucination) would need to reinvent this infrastructure independently.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `EvalCase` | dataclass | One input/expected-output pair passed to the harness. |
| `EvalResult` | dataclass | Outcome of running an agent on one `EvalCase`. |
| `EvalReport` | dataclass | Aggregated statistics across a full evaluation run. |
| `Metric` | Protocol | Structural interface for scoring functions. |
| `ExactMatchMetric` | class | Scores 1.0 on case-sensitive exact equality, 0.0 otherwise. |
| `ContainsMetric` | class | Scores 1.0 when expected string appears anywhere in actual (case-insensitive). |
| `NormalizedMatchMetric` | class | Scores 1.0 on case-insensitive, whitespace-stripped equality. |
| `EvalHarness` | class | Async runner that executes `agent_fn` over a list of `EvalCase` objects. |
| `aggregate` | function | Reduces a flat list of `EvalResult` into an `EvalReport`. |

### EvalCase

```
EvalCase(
    input: str,
    expected_output: str,
    metadata: dict[str, Any] = {},
    case_id: str = "",
)
```

### EvalResult

```
EvalResult(
    case: EvalCase,
    actual_output: str,
    score: float,
    latency_s: float,
    success: bool = True,
    run_index: int = 0,
    error: str | None = None,
)
```

### EvalReport

```
EvalReport(
    total_cases: int,
    total_runs: int,
    mean_score: float,
    min_score: float,
    max_score: float,
    std_score: float,
    pass_rate: float,
    threshold: float,
    results: list[EvalResult],
)
```

### EvalHarness

```
EvalHarness(
    agent_fn: Callable[[str], Coroutine[Any, Any, str]],
    metric: Any,
    threshold: float = 0.5,
)

async run(
    cases: list[EvalCase],
    *,
    repeat: int = 1,
) -> list[EvalResult]
```

`run` returns `len(cases) * repeat` results in case-then-repeat order.

### Metric Protocol

```
score(expected: str, actual: str) -> float
```

Returns a float in `[0.0, 1.0]`. Any object implementing this signature satisfies the `Metric` protocol without inheriting from it (`@runtime_checkable`).

### aggregate

```
aggregate(
    results: list[EvalResult],
    threshold: float = 0.5,
) -> EvalReport
```

Computes mean, min, max, sample standard deviation, and pass rate over `results`.

---

## Architecture

### Conceptual view

```
          EvalCase list
               |
               v
         EvalHarness
         /          \
   agent_fn       Metric
   (async)       .score()
         \          /
          EvalResult list
               |
               v
           aggregate()
               |
               v
           EvalReport
```

Three layers: data model, execution, aggregation. Each layer is self-contained. The harness depends on models and the metric protocol but not on any particular metric implementation. `aggregate` depends only on models.

### Data flow

1. The caller constructs one `EvalCase` per test input, providing the raw `input` string and the `expected_output` reference.
2. `EvalHarness.run(cases, repeat=N)` iterates over every case. For each case it calls `_run_one` N times (for variance estimation).
3. Inside `_run_one`, `time.perf_counter()` brackets the `await agent_fn(case.input)` call to measure wall-clock latency.
4. If `agent_fn` raises, the exception message is captured in `EvalResult.error` and the score is forced to `0.0`.
5. Otherwise `metric.score(case.expected_output, actual)` returns a float in `[0.0, 1.0]`. `success` is set to `True` when `score >= threshold`.
6. All `EvalResult` objects are collected into a flat list and returned.
7. `aggregate(results, threshold)` computes statistics using `statistics.mean`, `statistics.stdev`, and a pass-rate count. It identifies unique cases via `id(r.case)` (object identity).
8. The caller receives an `EvalReport` and can inspect per-result details via `report.results`.

### Key abstractions

**EvalCase** models a single test vector. The `case_id` field is optional and intended for traceability back to a source dataset row. `metadata` carries arbitrary labels (e.g., difficulty tier, domain tag) that downstream aggregation can use for slice analysis.

**EvalResult** is the atomic output unit. It contains both the numeric `score` and the raw `actual_output` string, enabling both machine-readable reporting and human review in the same object. Storing `latency_s` here rather than in a separate profiling pass means cost and quality data stay co-located.

**Metric Protocol** is structural (`@runtime_checkable`). Callers can pass any object with a `score(expected, actual) -> float` method — no inheritance required. This keeps the harness decoupled from the metric library and allows custom metrics written in any style.

**EvalHarness** accepts the `agent_fn` as a constructor argument rather than a method argument. This allows the harness to be constructed once and reused across multiple `run` calls with different case sets, which is useful in the prompt comparison module.

---

## Design decisions and tradeoffs

- **Decision**: All three built-in metrics return binary scores (0.0 or 1.0) rather than graduated scores. **Why**: Binary scores are simple to interpret, easy to threshold, and compose well with pass-rate reporting. **Tradeoff**: Partial credit (e.g., BLEU, F1) requires a custom `Metric` implementation; it is not provided out of the box.

- **Decision**: `aggregate` uses `id(r.case)` to count unique cases. **Why**: Avoids requiring `EvalCase` to be hashable or comparable, which would force structural equality definitions on a data class that may contain mutable `metadata` dicts. **Tradeoff**: If the same case object is used across multiple harness runs (e.g., two separate `EvalHarness` instances), the identity count still works correctly. However, if cases are reconstructed from the same data, they get different identities and `total_cases` will be overcounted.

- **Decision**: `std_score` is zero when only one run is executed. **Why**: `statistics.stdev` requires at least two data points; returning 0.0 avoids a `StatisticsError` and is numerically correct (no variance from a single sample). **Tradeoff**: The caller must check `total_runs > 1` before interpreting `std_score` as meaningful variance.

- **Decision**: Exceptions from `agent_fn` are caught with a broad `except Exception` inside `_run_one` and stored in `error`. **Why**: Evaluation runs may call remote APIs that can fail transiently. Crashing the entire harness on one bad case would discard all other results. **Tradeoff**: Silent swallowing can mask bugs in the agent; callers must inspect `error` fields to detect failures.

---

## Scaling concerns

The harness is single-threaded sequential: it awaits each case before starting the next. For small evaluation sets (tens to low hundreds of cases) this is not a bottleneck. As case counts grow into the thousands, sequential execution becomes the dominant cost because each agent call incurs network latency. There is no concurrency primitive in the current implementation (no `asyncio.gather` or semaphore). The `repeat` parameter multiplies latency linearly. Memory usage is proportional to `len(cases) * repeat` for the `EvalResult` list, which is modest for typical evaluation workloads. The aggregation step is O(n) and not a bottleneck.

**What breaks first**: wall-clock runtime when evaluating against slow remote LLM APIs at scale.

**Ceiling**: practical ceiling is roughly 100-500 cases with `repeat=1` per run before runtime becomes unacceptable in interactive use. Batch or concurrent evaluation is not implemented.

---

## Future improvements

- **Concurrent execution**: replace the sequential loop in `EvalHarness.run` with `asyncio.gather` and a configurable concurrency limit (semaphore). This would allow saturating rate limits rather than spending most time waiting.
- **Streaming results**: yield `EvalResult` objects as they complete rather than collecting all into a list. This enables early stopping and progress reporting for large case sets.
- **Graduated metrics**: add BLEU, ROUGE, BERTScore, and semantic similarity metrics to the built-in set to support NLG evaluation use cases beyond exact/substring match.
- **Slice analysis in EvalReport**: extend `aggregate` to compute per-metadata-tag breakdowns, enabling failure analysis by domain, difficulty, or annotator.
- **Deterministic unique case counting**: require `EvalCase` to carry a mandatory `case_id` and use it for deduplication instead of `id()`, removing the object-identity ambiguity.

---

## Usage examples

Basic harness run with exact match:

```python
import asyncio
from llm_agents.evaluation.framework import (
    EvalCase, EvalHarness, ExactMatchMetric, aggregate
)

async def my_agent(input: str) -> str:
    return "4"  # stub

cases = [
    EvalCase(input="2+2", expected_output="4", case_id="add-1"),
    EvalCase(input="3-1", expected_output="2", case_id="sub-1"),
]

harness = EvalHarness(agent_fn=my_agent, metric=ExactMatchMetric(), threshold=0.5)
results = asyncio.run(harness.run(cases, repeat=1))
report = aggregate(results)
print(report.mean_score, report.pass_rate)
```

Variance estimation with repeat runs:

```python
harness = EvalHarness(agent_fn=my_agent, metric=NormalizedMatchMetric())
results = asyncio.run(harness.run(cases, repeat=5))
report = aggregate(results, threshold=0.5)
print(f"std={report.std_score:.3f}, pass_rate={report.pass_rate:.2f}")
```

Custom metric:

```python
from llm_agents.evaluation.framework import EvalHarness, aggregate

class LenRatioMetric:
    def score(self, expected: str, actual: str) -> float:
        if not expected:
            return 1.0 if not actual else 0.0
        return min(len(actual) / len(expected), 1.0)

harness = EvalHarness(agent_fn=my_agent, metric=LenRatioMetric())
results = asyncio.run(harness.run(cases))
report = aggregate(results)
```
