"""Evaluation harness: run an agent callable over a case set.

:class:`EvalHarness` accepts any async callable with the signature
``agent_fn(input: str) -> str`` and a :class:`Metric` (or any object with a
``score(expected, actual) -> float`` method).  It iterates over the provided
:class:`EvalCase` list, optionally repeating each case *N* times for
variance measurement.

:func:`aggregate` reduces a flat list of :class:`EvalResult` objects into an
:class:`EvalReport` with mean/min/max/std scores and a pass rate.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Coroutine
from typing import Any

from llm_agents.evaluation.framework._models import (
    EvalCase,
    EvalReport,
    EvalResult,
)


class EvalHarness:
    """Runs an agent function over an evaluation case set.

    Args:
        agent_fn: Async callable ``(input: str) -> str``.  Should never raise;
                  exceptions are caught and stored in :attr:`EvalResult.error`.
        metric:   Object with ``score(expected, actual) -> float``.
        threshold: Passing threshold for ``EvalResult.success``.  Default 0.5.
    """

    def __init__(
        self,
        agent_fn: Callable[[str], Coroutine[Any, Any, str]],
        metric: Any,
        threshold: float = 0.5,
    ) -> None:
        self._agent_fn = agent_fn
        self._metric = metric
        self._threshold = threshold

    async def run(
        self,
        cases: list[EvalCase],
        *,
        repeat: int = 1,
    ) -> list[EvalResult]:
        """Evaluate *agent_fn* on each case in *cases*.

        Args:
            cases:  List of :class:`EvalCase` objects to evaluate.
            repeat: Number of times to run each case (for variance estimation).
                    Defaults to 1.

        Returns:
            Flat list of :class:`EvalResult` objects (``len(cases) * repeat``
            entries total, in case-then-repeat order).
        """
        results: list[EvalResult] = []
        for case in cases:
            for run_idx in range(repeat):
                result = await self._run_one(case, run_idx)
                results.append(result)
        return results

    async def _run_one(self, case: EvalCase, run_index: int) -> EvalResult:
        t0 = time.perf_counter()
        actual = ""
        error: str | None = None
        try:
            actual = await self._agent_fn(case.input)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        latency_s = time.perf_counter() - t0

        score = 0.0 if error else self._metric.score(case.expected_output, actual)
        return EvalResult(
            case=case,
            actual_output=actual,
            score=score,
            latency_s=latency_s,
            success=score >= self._threshold,
            run_index=run_index,
            error=error,
        )


def aggregate(
    results: list[EvalResult],
    threshold: float = 0.5,
) -> EvalReport:
    """Aggregate a flat list of :class:`EvalResult` objects into an :class:`EvalReport`.

    Args:
        results:   All :class:`EvalResult` objects from one or more harness runs.
        threshold: Passing threshold for ``pass_rate`` computation.

    Returns:
        :class:`EvalReport` with mean/min/max/std scores and pass rate.
    """
    if not results:
        return EvalReport(threshold=threshold)

    scores = [r.score for r in results]
    unique_cases = {id(r.case) for r in results}

    mean = statistics.mean(scores)
    std = statistics.stdev(scores) if len(scores) > 1 else 0.0
    passed = sum(1 for s in scores if s >= threshold)

    return EvalReport(
        total_cases=len(unique_cases),
        total_runs=len(results),
        mean_score=mean,
        min_score=min(scores),
        max_score=max(scores),
        std_score=std,
        pass_rate=passed / len(scores),
        threshold=threshold,
        results=results,
    )
