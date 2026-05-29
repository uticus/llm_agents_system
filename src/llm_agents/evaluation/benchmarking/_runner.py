"""Benchmark runner: execute a suite and aggregate metrics into a report.

:class:`BenchmarkRunner` drives an async agent callable over all tasks in a
:class:`Suite`, collects :class:`TaskResult` objects, and produces a
:class:`BenchmarkReport` with aggregated statistics.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Coroutine
from typing import Any

from llm_agents.evaluation.benchmarking._models import (
    BenchmarkReport,
    BenchmarkTask,
    Suite,
    TaskResult,
)


class BenchmarkRunner:
    """Runs a :class:`Suite` against an agent callable.

    The callable signature is::

        async def agent_fn(input: str) -> AgentOutput

    where :class:`AgentOutput` is any object with:
    - ``.output: str`` — the text output
    - ``.prompt_tokens: int`` — (optional, default 0)
    - ``.completion_tokens: int`` — (optional, default 0)
    - ``.cost_usd: float`` — (optional, default 0.0)
    - ``.cache_hit: bool`` — (optional, default False)

    A plain ``str`` is also accepted (all metadata fields default to 0).

    Args:
        agent_fn:  Async callable that receives a task input and returns
                   an output (string or AgentOutput-compatible object).
        scorer:    Callable ``(expected: str, actual: str) -> bool``.
                   Defaults to exact string equality.
    """

    def __init__(
        self,
        agent_fn: Callable[[str], Coroutine[Any, Any, Any]],
        scorer: Callable[[str, str], bool] | None = None,
    ) -> None:
        self._agent_fn = agent_fn
        self._scorer = scorer or (lambda expected, actual: actual == expected)

    async def run(self, suite: Suite) -> BenchmarkReport:
        """Execute all tasks in *suite* and return a :class:`BenchmarkReport`.

        Args:
            suite: The :class:`Suite` to run.

        Returns:
            :class:`BenchmarkReport` with per-task results and aggregated metrics.
        """
        results: list[TaskResult] = []
        for task in suite.tasks:
            result = await self._run_task(task)
            results.append(result)

        return _build_report(suite.name, results)

    async def _run_task(self, task: BenchmarkTask) -> TaskResult:
        t0 = time.perf_counter()
        error: str | None = None
        output_str = ""
        prompt_tokens = 0
        completion_tokens = 0
        cost_usd = 0.0
        cache_hit = False

        try:
            raw = await self._agent_fn(task.input)
            if isinstance(raw, str):
                output_str = raw
            else:
                output_str = getattr(raw, "output", str(raw))
                prompt_tokens = int(getattr(raw, "prompt_tokens", 0))
                completion_tokens = int(getattr(raw, "completion_tokens", 0))
                cost_usd = float(getattr(raw, "cost_usd", 0.0))
                cache_hit = bool(getattr(raw, "cache_hit", False))
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"

        latency_s = time.perf_counter() - t0
        success = error is None and self._scorer(task.expected_output, output_str)

        return TaskResult(
            task_id=task.task_id,
            success=success,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_s=latency_s,
            cost_usd=cost_usd,
            cache_hit=cache_hit,
            actual_output=output_str,
            error=error,
        )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _build_report(suite_name: str, results: list[TaskResult]) -> BenchmarkReport:
    if not results:
        return BenchmarkReport(suite_name=suite_name)

    n = len(results)
    success_rate = sum(1 for r in results if r.success) / n
    mean_tokens = sum(r.prompt_tokens + r.completion_tokens for r in results) / n
    latencies = [r.latency_s for r in results]
    mean_latency = statistics.mean(latencies)
    p95_latency = _percentile(latencies, 95)
    mean_cost = sum(r.cost_usd for r in results) / n
    cache_hit_rate = sum(1 for r in results if r.cache_hit) / n

    return BenchmarkReport(
        suite_name=suite_name,
        task_results=results,
        success_rate=success_rate,
        mean_tokens=mean_tokens,
        mean_latency_s=mean_latency,
        p95_latency_s=p95_latency,
        mean_cost_usd=mean_cost,
        cache_hit_rate=cache_hit_rate,
    )


def _percentile(data: list[float], p: int) -> float:
    """Return the *p*-th percentile of *data* (nearest-rank method)."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    # Nearest-rank: ceil(p/100 * n) - 1 (0-indexed)
    rank = max(0, int(p / 100 * n + 0.999) - 1)
    return sorted_data[min(rank, n - 1)]
