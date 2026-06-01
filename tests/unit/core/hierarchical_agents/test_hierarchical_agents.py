"""Unit tests for core/hierarchical_agents.

Covers AgentResult/SupervisorResult models, Worker (LLM path), Supervisor
delegation (sequential and parallel), worker failure handling, and tracing
spans.  No real network calls.
"""

from __future__ import annotations

import asyncio

import pytest

from llm_agents.core.hierarchical_agents import (
    Agent,
    AgentResult,
    Supervisor,
    SupervisorResult,
    Worker,
)
from llm_agents.core.planning import LLMPlanner, SequentialPlanner
from llm_agents.infra.inference_routing._models import (
    Candidate,
    LLMResponse,
    RoutingPolicy,
)
from llm_agents.infra.inference_routing._provider import FakeProvider
from llm_agents.infra.inference_routing._router import Router
from llm_agents.infra.tracing import get_collector
from llm_agents.infra.tracing._models import SpanKind, SpanStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_collector():
    get_collector().reset()
    yield
    get_collector().reset()


def _fake_response(content: str) -> LLMResponse:
    return LLMResponse(
        model="fake",
        content=content,
        prompt_tokens=10,
        completion_tokens=5,
        latency_s=0.0,
    )


def _router_with_responses(*contents: str) -> Router:
    responses = [_fake_response(c) for c in contents]
    provider = FakeProvider("fake", responses)
    policy = RoutingPolicy(candidates=[Candidate(provider=provider, model="fake")])
    return Router(policy, export_hook=None)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class _MockWorker:
    """Worker stub that returns a fixed response or raises on demand."""

    def __init__(self, response: str | Exception) -> None:
        self._response = response
        self.call_count = 0
        self.received_tasks: list[str] = []

    async def run(self, task: str) -> AgentResult:
        self.call_count += 1
        self.received_tasks.append(task)
        if isinstance(self._response, Exception):
            return AgentResult.err(task=task, error=str(self._response))
        return AgentResult.ok(task=task, output=self._response)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_agent_result_ok():
    """AgentResult.ok() sets success=True."""
    r = AgentResult.ok("do thing", "done")
    assert r.success is True
    assert r.output == "done"
    assert r.error is None


def test_agent_result_err():
    """AgentResult.err() sets success=False."""
    r = AgentResult.err("do thing", "boom")
    assert r.success is False
    assert r.output is None
    assert r.error == "boom"


def test_supervisor_result_defaults():
    """SupervisorResult defaults to success=True and empty results."""
    sr = SupervisorResult(goal="my goal")
    assert sr.success is True
    assert sr.failed_count == 0
    assert sr.results == []


# ---------------------------------------------------------------------------
# T1: Agent protocol
# ---------------------------------------------------------------------------


def test_agent_protocol_worker():
    """T1: Worker satisfies the Agent protocol at runtime."""
    router = _router_with_responses("ok")
    w = Worker(router=router)
    assert isinstance(w, Agent)


def test_agent_protocol_mock():
    """T1b: _MockWorker satisfies the Agent protocol at runtime."""
    assert isinstance(_MockWorker("ok"), Agent)


# ---------------------------------------------------------------------------
# T2: Worker — LLM path
# ---------------------------------------------------------------------------


def test_worker_llm_success():
    """T2: Worker routes the task to the LLM and returns a successful AgentResult."""
    router = _router_with_responses("computed answer")
    worker = Worker(router=router, model="fake")
    result = asyncio.run(worker.run("compute 2 + 2"))
    assert result.success is True
    assert result.output == "computed answer"
    assert result.task == "compute 2 + 2"


def test_worker_llm_failure_captured():
    """T2b: Worker captures LLM errors and returns AgentResult with success=False."""
    provider = FakeProvider("fail", [RuntimeError("network error")])
    policy = RoutingPolicy([Candidate(provider, "fake")], max_retries=0)
    router = Router(policy, export_hook=None)
    worker = Worker(router=router, model="fake")
    result = asyncio.run(worker.run("some task"))
    assert result.success is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# T3: Supervisor — sequential delegation
# ---------------------------------------------------------------------------


def test_supervisor_sequential_delegates_to_worker():
    """T3: Supervisor decomposes goal and delegates each step to the worker."""
    planner = SequentialPlanner(model="fake")
    worker = _MockWorker("worker answer")
    supervisor = Supervisor(planner=planner, workers=[worker])
    sr = asyncio.run(supervisor.run("do one thing"))
    assert isinstance(sr, SupervisorResult)
    assert sr.goal == "do one thing"
    assert worker.call_count == 1
    assert sr.success is True


def test_supervisor_multi_step_all_done():
    """T3b: Supervisor handles multi-step plans; all workers return success."""
    planner_router = _router_with_responses("STEP: step one\nSTEP: step two\nSTEP: step three")
    planner = LLMPlanner(router=planner_router, model="fake")
    worker = _MockWorker("ok")
    supervisor = Supervisor(planner=planner, workers=[worker])
    sr = asyncio.run(supervisor.run("three-part goal"))
    assert len(sr.results) == 3
    assert sr.success is True
    assert sr.failed_count == 0
    assert worker.call_count == 3


def test_supervisor_passes_step_description_to_worker():
    """T3c: Worker receives the step description as its task string."""
    planner_router = _router_with_responses("STEP: gather metrics\nSTEP: compute average")
    planner = LLMPlanner(router=planner_router, model="fake")
    worker = _MockWorker("done")
    supervisor = Supervisor(planner=planner, workers=[worker])
    asyncio.run(supervisor.run("analyze data"))
    assert "gather metrics" in worker.received_tasks
    assert "compute average" in worker.received_tasks


# ---------------------------------------------------------------------------
# T4: Supervisor — worker failure handling
# ---------------------------------------------------------------------------


def test_supervisor_worker_failure_does_not_abort():
    """T4: A failing worker is recorded; remaining workers still execute."""
    planner_router = _router_with_responses("STEP: step one\nSTEP: step two\nSTEP: step three")
    planner = LLMPlanner(router=planner_router, model="fake")

    class _AlternatingWorker:
        """Fails on every odd call (1-indexed), succeeds on even."""

        call_count = 0
        received_tasks: list[str] = []

        async def run(self, task: str) -> AgentResult:
            self.call_count += 1
            self.received_tasks.append(task)
            if self.call_count % 2 == 1:
                return AgentResult.err(task=task, error="odd failure")
            return AgentResult.ok(task=task, output="even ok")

    worker = _AlternatingWorker()
    supervisor = Supervisor(planner=planner, workers=[worker])
    sr = asyncio.run(supervisor.run("three steps"))

    assert len(sr.results) == 3, "All three steps must produce results"
    assert worker.call_count == 3, "All workers must be called"
    # Steps 1 and 3 fail (odd), step 2 succeeds (even)
    assert sr.results[0].success is False
    assert sr.results[1].success is True
    assert sr.results[2].success is False
    assert sr.success is False
    assert sr.failed_count == 2


def test_supervisor_single_worker_failure_captured():
    """T4b: A single failing step is captured; SupervisorResult.success is False."""
    planner = SequentialPlanner(model="fake")
    worker = _MockWorker(RuntimeError("boom"))
    supervisor = Supervisor(planner=planner, workers=[worker])
    sr = asyncio.run(supervisor.run("failing goal"))
    assert sr.success is False
    assert sr.failed_count == 1
    assert sr.results[0].success is False


# ---------------------------------------------------------------------------
# T5: Supervisor — parallel delegation
# ---------------------------------------------------------------------------


def test_supervisor_parallel_all_succeed():
    """T5: Parallel delegation returns results for all steps."""
    planner_router = _router_with_responses("STEP: a\nSTEP: b\nSTEP: c")
    planner = LLMPlanner(router=planner_router, model="fake")
    worker = _MockWorker("parallel ok")
    supervisor = Supervisor(planner=planner, workers=[worker], parallel=True)
    sr = asyncio.run(supervisor.run("parallel goal"))
    assert len(sr.results) == 3
    assert sr.success is True


# ---------------------------------------------------------------------------
# T6: Supervisor requires at least one worker
# ---------------------------------------------------------------------------


def test_supervisor_requires_workers():
    """T6: Supervisor raises ValueError when workers list is empty."""
    planner = SequentialPlanner()
    with pytest.raises(ValueError, match="at least one worker"):
        Supervisor(planner=planner, workers=[])


# ---------------------------------------------------------------------------
# T7: round-robin worker assignment
# ---------------------------------------------------------------------------


def test_supervisor_round_robin_two_workers():
    """T7: With two workers, steps are distributed round-robin."""
    planner_router = _router_with_responses("STEP: task a\nSTEP: task b\nSTEP: task c")
    planner = LLMPlanner(router=planner_router, model="fake")
    w1 = _MockWorker("w1")
    w2 = _MockWorker("w2")
    supervisor = Supervisor(planner=planner, workers=[w1, w2])
    sr = asyncio.run(supervisor.run("three tasks"))
    assert len(sr.results) == 3
    # w1 gets steps 0, 2; w2 gets step 1
    assert w1.call_count == 2
    assert w2.call_count == 1


# ---------------------------------------------------------------------------
# T8: tracing spans
# ---------------------------------------------------------------------------


def test_supervisor_emits_agent_span_on_success():
    """T8: Supervisor.run() emits a SpanKind.AGENT span with status OK."""
    planner = SequentialPlanner(model="fake")
    worker = _MockWorker("done")
    supervisor = Supervisor(planner=planner, workers=[worker])
    asyncio.run(supervisor.run("trace me"))

    collector = get_collector()
    all_spans = [s for t in collector.all_traces() for s in t.spans]
    agent_spans = [s for s in all_spans if s.kind == SpanKind.AGENT]
    sup_span = next(s for s in agent_spans if s.name == "supervisor:run")
    assert sup_span.status == SpanStatus.OK


def test_supervisor_emits_agent_span_on_failure():
    """T8b: Supervisor.run() span has ERROR status when any worker fails."""
    planner = SequentialPlanner(model="fake")
    worker = _MockWorker(RuntimeError("fail"))
    supervisor = Supervisor(planner=planner, workers=[worker])
    asyncio.run(supervisor.run("fail trace"))

    collector = get_collector()
    all_spans = [s for t in collector.all_traces() for s in t.spans]
    sup_span = next(s for s in all_spans if s.name == "supervisor:run" and s.kind == SpanKind.AGENT)
    assert sup_span.status == SpanStatus.ERROR
