"""Supervisor: decomposes a goal and delegates subtasks to worker agents.

:class:`Supervisor` uses a :class:`Planner` to decompose a goal string into
:class:`Step` objects, then delegates each step to a :class:`Worker` (or any
:class:`Agent`-compatible object).  Results are aggregated into a
:class:`SupervisorResult`.  Worker failures are recorded but do not abort
the remaining delegations.

A :data:`SpanKind.AGENT` tracing span is emitted for each
:meth:`Supervisor.run` invocation.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from llm_agents.core.hierarchical_agents._models import AgentResult, SupervisorResult
from llm_agents.infra.tracing import tracer
from llm_agents.infra.tracing._models import SpanKind, SpanStatus

if TYPE_CHECKING:
    from llm_agents.core.planning._planner import Planner


class Supervisor:
    """Coordinates a pool of worker agents to achieve a goal.

    Args:
        planner: :class:`Planner` used to decompose the goal into subtasks.
        workers: Sequence of :class:`Agent`-compatible workers.  Tasks are
                 distributed round-robin across available workers; a single
                 worker is used for all tasks when only one is provided.
        parallel: When ``True`` all subtasks are dispatched concurrently with
                  :func:`asyncio.gather`.  When ``False`` (default) they are
                  executed sequentially to simplify debugging and tracing.
    """

    def __init__(
        self,
        planner: Planner,
        workers: list[Any],
        *,
        parallel: bool = False,
    ) -> None:
        if not workers:
            raise ValueError("Supervisor requires at least one worker.")
        self._planner = planner
        self._workers = workers
        self._parallel = parallel

    async def run(self, goal: str) -> SupervisorResult:
        """Decompose *goal* and delegate subtasks to workers.

        Steps:
        1. Call :meth:`Planner.plan` to produce a :class:`Plan`.
        2. Assign each :class:`Step` to a worker (round-robin).
        3. Execute all delegations (sequential or parallel).
        4. Collect :class:`AgentResult` objects and build a
           :class:`SupervisorResult`.

        Worker failures are captured in the corresponding :class:`AgentResult`
        and do not prevent other tasks from running.

        Args:
            goal: Natural-language goal string.

        Returns:
            :class:`SupervisorResult` with one :class:`AgentResult` per step.
        """
        async with tracer.span(
            "supervisor:run",
            kind=SpanKind.AGENT,
            goal=goal,
        ) as span:
            plan = await self._planner.plan(goal)
            steps = plan.steps

            if self._parallel:
                results = await self._delegate_parallel(steps)
            else:
                results = await self._delegate_sequential(steps)

            failed = [r for r in results if not r.success]
            supervisor_result = SupervisorResult(
                goal=goal,
                results=results,
                success=len(failed) == 0,
                failed_count=len(failed),
            )

            if failed:
                span.status = SpanStatus.ERROR
                span.attributes["failed_count"] = len(failed)
            else:
                span.status = SpanStatus.OK

            return supervisor_result

    async def _delegate_sequential(self, steps: list[Any]) -> list[AgentResult]:
        results: list[AgentResult] = []
        for i, step in enumerate(steps):
            worker = self._workers[i % len(self._workers)]
            result = await worker.run(step.description)
            results.append(result)
        return results

    async def _delegate_parallel(self, steps: list[Any]) -> list[AgentResult]:
        tasks = [
            self._workers[i % len(self._workers)].run(step.description)
            for i, step in enumerate(steps)
        ]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        results: list[AgentResult] = []
        for i, item in enumerate(raw):
            step = steps[i]
            if isinstance(item, BaseException):
                results.append(
                    AgentResult.err(
                        task=step.description,
                        error=f"{type(item).__name__}: {item}",
                    )
                )
            else:
                results.append(item)
        return results
