"""Unit tests for core/planning.

Covers plan models, planner strategies (SequentialPlanner, LLMPlanner),
step execution (tool and LLM paths), replanning on failure, halt on
unrecoverable failure, memory context injection, and tracing spans.
No real network calls.
"""

from __future__ import annotations

import asyncio

import pytest

from llm_agents.core.planning import (
    LLMPlanner,
    Plan,
    Planner,
    PlanStatus,
    SequentialPlanner,
    Step,
    StepStatus,
    execute,
)
from llm_agents.core.planning._planner import _parse_steps
from llm_agents.core.tool_orchestration import Tool, ToolDispatcher, ToolRegistry
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
    """Return a Router backed by a FakeProvider yielding *contents* in order."""
    responses = [_fake_response(c) for c in contents]
    provider = FakeProvider("fake", responses)
    policy = RoutingPolicy(candidates=[Candidate(provider=provider, model="fake")])
    return Router(policy, export_hook=None)


def _empty_dispatcher() -> ToolDispatcher:
    return ToolDispatcher(ToolRegistry())


def _router_noop() -> Router:
    """Return a Router with a single dummy response that should not be called in tool tests."""
    provider = FakeProvider("noop", [_fake_response("(unused)")])
    policy = RoutingPolicy(candidates=[Candidate(provider=provider, model="noop")])
    return Router(policy, export_hook=None)


def _dispatcher_with_add() -> ToolDispatcher:
    async def add(a: float, b: float) -> float:
        return a + b

    tool = Tool(
        name="add",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
        fn=add,
    )
    reg = ToolRegistry()
    reg.register(tool)
    return ToolDispatcher(reg)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_step_defaults():
    """Step initialises with PENDING status and auto-generated id."""
    step = Step(description="do something")
    assert step.status == StepStatus.PENDING
    assert step.tool_name is None
    assert step.result is None
    assert step.error is None
    assert step.id  # non-empty auto-generated UUID


def test_plan_defaults():
    """Plan initialises with PENDING status."""
    plan = Plan(goal="achieve x", steps=[Step(description="step 1")])
    assert plan.status == PlanStatus.PENDING
    assert len(plan.steps) == 1


# ---------------------------------------------------------------------------
# T1: SequentialPlanner
# ---------------------------------------------------------------------------


def test_sequential_planner_single_step():
    """T1: SequentialPlanner produces exactly one step for any goal."""
    planner = SequentialPlanner(model="gpt-test")
    plan = asyncio.run(planner.plan("compute 1 + 2"))
    assert isinstance(plan, Plan)
    assert len(plan.steps) == 1
    assert plan.steps[0].status == StepStatus.PENDING
    assert "compute 1 + 2" in plan.steps[0].description


def test_sequential_planner_goal_preserved():
    """T1b: SequentialPlanner sets plan.goal to the original goal string."""
    planner = SequentialPlanner()
    plan = asyncio.run(planner.plan("my special goal"))
    assert plan.goal == "my special goal"


# ---------------------------------------------------------------------------
# T2: _parse_steps
# ---------------------------------------------------------------------------


def test_parse_steps_basic():
    """T2: _parse_steps extracts STEP: lines."""
    text = "STEP: gather data\nSTEP: process data\nSTEP: summarize"
    steps = _parse_steps(text)
    assert len(steps) == 3
    assert steps[0].description == "gather data"
    assert steps[2].description == "summarize"


def test_parse_steps_ignores_non_step_lines():
    """T2b: Lines not starting with STEP: are ignored."""
    text = "Here is your plan:\nSTEP: first action\nNote: do carefully\nSTEP: second action"
    steps = _parse_steps(text)
    assert len(steps) == 2
    assert steps[0].description == "first action"
    assert steps[1].description == "second action"


def test_parse_steps_case_insensitive():
    """T2c: STEP: prefix matching is case-insensitive."""
    text = "step: lowercase\nStep: mixed"
    steps = _parse_steps(text)
    assert len(steps) == 2


def test_parse_steps_empty_returns_empty():
    """T2d: Empty or step-free text returns an empty list."""
    assert _parse_steps("") == []
    assert _parse_steps("No steps here at all.") == []


# ---------------------------------------------------------------------------
# T3: LLMPlanner
# ---------------------------------------------------------------------------


def test_llm_planner_parses_multi_step():
    """T3: LLMPlanner calls the mock LLM and parses STEP: lines."""
    router = _router_with_responses(
        "STEP: gather data\nSTEP: process data\nSTEP: summarize results"
    )
    planner = LLMPlanner(router=router, model="fake")
    plan = asyncio.run(planner.plan("analyze data"))
    assert isinstance(plan, Plan)
    assert len(plan.steps) == 3
    assert "gather data" in plan.steps[0].description
    assert "process data" in plan.steps[1].description
    assert "summarize results" in plan.steps[2].description


def test_llm_planner_fallback_on_empty_response():
    """T3b: LLMPlanner falls back to single-step plan when LLM returns no STEP: lines."""
    router = _router_with_responses("I cannot break this down.")
    planner = LLMPlanner(router=router, model="fake")
    plan = asyncio.run(planner.plan("do something"))
    assert len(plan.steps) == 1
    assert plan.steps[0].description == "do something"


# ---------------------------------------------------------------------------
# T4: Planner protocol
# ---------------------------------------------------------------------------


def test_planner_protocol_sequential():
    """T4: SequentialPlanner satisfies the Planner protocol at runtime."""
    assert isinstance(SequentialPlanner(), Planner)


def test_planner_protocol_llm():
    """T4b: LLMPlanner satisfies the Planner protocol at runtime."""
    router = _router_with_responses("STEP: a")
    assert isinstance(LLMPlanner(router=router), Planner)


# ---------------------------------------------------------------------------
# T5: execute() — tool step
# ---------------------------------------------------------------------------


def test_execute_tool_step_success():
    """T5: execute() dispatches a tool step and marks it DONE with the tool output."""
    step = Step(
        description="add 3 and 4",
        tool_name="add",
        tool_arguments={"a": 3.0, "b": 4.0},
    )
    plan = Plan(goal="add numbers", steps=[step])
    dispatcher = _dispatcher_with_add()
    router = _router_noop()

    result_plan = asyncio.run(execute(plan, dispatcher, router))
    assert result_plan.status == PlanStatus.DONE
    assert result_plan.steps[0].status == StepStatus.DONE
    assert result_plan.steps[0].result == pytest.approx(7.0)


def test_execute_unknown_tool_fails_step():
    """T5b: A tool step with an unknown tool name marks the step FAILED."""
    step = Step(
        description="call ghost tool",
        tool_name="ghost",
        tool_arguments={},
    )
    plan = Plan(goal="call ghost", steps=[step])
    dispatcher = _empty_dispatcher()
    router = _router_noop()

    result_plan = asyncio.run(execute(plan, dispatcher, router, max_replan=0))
    assert result_plan.status == PlanStatus.FAILED
    assert result_plan.steps[0].status == StepStatus.FAILED
    assert result_plan.steps[0].error is not None


# ---------------------------------------------------------------------------
# T6: execute() — LLM step
# ---------------------------------------------------------------------------


def test_execute_llm_step_success():
    """T6: execute() calls the router for an LLM step and marks it DONE."""
    step = Step(description="explain gravity", tool_arguments={"model": "fake"})
    plan = Plan(goal="explain gravity", steps=[step])
    router = _router_with_responses("Gravity is the force of attraction.")
    dispatcher = _empty_dispatcher()

    result_plan = asyncio.run(execute(plan, dispatcher, router))
    assert result_plan.status == PlanStatus.DONE
    assert result_plan.steps[0].status == StepStatus.DONE
    assert "Gravity" in result_plan.steps[0].result


def test_execute_multiple_llm_steps():
    """T6b: execute() handles multiple sequential LLM steps."""
    steps = [
        Step(description="step one"),
        Step(description="step two"),
        Step(description="step three"),
    ]
    plan = Plan(goal="three things", steps=steps)
    router = _router_with_responses("answer one", "answer two", "answer three")
    dispatcher = _empty_dispatcher()

    result_plan = asyncio.run(execute(plan, dispatcher, router))
    assert result_plan.status == PlanStatus.DONE
    assert all(s.status == StepStatus.DONE for s in result_plan.steps)


# ---------------------------------------------------------------------------
# T7: replanning on failure
# ---------------------------------------------------------------------------


class _FixedPlanner:
    """Planner that always returns a fixed single-step plan."""

    def __init__(self, step_description: str) -> None:
        self._desc = step_description
        self.call_count = 0

    async def plan(self, goal: str, context: str = "") -> Plan:
        self.call_count += 1
        return Plan(goal=goal, steps=[Step(description=self._desc)])


def test_execute_replanning_on_step_failure():
    """T7: A failing LLM step triggers replanning; the replacement step succeeds.

    The provider raises on the first call (original step fails) and succeeds on
    the second call (replacement step from the planner succeeds).
    """
    # Single provider: first call raises, second call returns a valid response.
    provider = FakeProvider(
        "p", [RuntimeError("boom"), _fake_response("recovered")]
    )
    router = Router(
        RoutingPolicy([Candidate(provider, "fake")], max_retries=0),
        export_hook=None,
    )

    # Planner injects a replacement step with the same description the router uses.
    fixed_planner = _FixedPlanner("retry step")

    step_orig = Step(description="try this", tool_arguments={"model": "fake"})
    plan = Plan(goal="do thing", steps=[step_orig])

    result_plan = asyncio.run(
        execute(plan, _empty_dispatcher(), router, planner=fixed_planner, max_replan=1)
    )

    assert fixed_planner.call_count == 1, "Planner must be called exactly once"
    assert result_plan.status == PlanStatus.DONE


def test_execute_replan_budget_exhausted_halts():
    """T7b: When max_replan=0, a failing step immediately halts execution."""
    provider = FakeProvider("p", [RuntimeError("always fails")])
    router = Router(
        RoutingPolicy([Candidate(provider, "fake")], max_retries=0),
        export_hook=None,
    )
    plan = Plan(goal="fail", steps=[Step(description="doomed step")])
    result_plan = asyncio.run(
        execute(plan, _empty_dispatcher(), router, max_replan=0)
    )
    assert result_plan.status == PlanStatus.FAILED
    assert result_plan.steps[0].status == StepStatus.FAILED


def test_execute_no_planner_fails_on_error():
    """T7c: Without a planner, a failing step marks the plan FAILED."""
    provider = FakeProvider("p", [RuntimeError("no recovery")])
    router = Router(
        RoutingPolicy([Candidate(provider, "fake")], max_retries=0),
        export_hook=None,
    )
    plan = Plan(goal="fail", steps=[Step(description="broken")])
    result_plan = asyncio.run(
        execute(plan, _empty_dispatcher(), router, planner=None)
    )
    assert result_plan.status == PlanStatus.FAILED


# ---------------------------------------------------------------------------
# T8: tracing spans
# ---------------------------------------------------------------------------


def test_execute_emits_agent_span():
    """T8: execute() emits a SpanKind.AGENT span with status OK on success."""
    step = Step(description="a step", tool_arguments={"model": "fake"})
    plan = Plan(goal="trace test", steps=[step])
    router = _router_with_responses("done")
    asyncio.run(execute(plan, _empty_dispatcher(), router))

    collector = get_collector()
    all_spans = [s for t in collector.all_traces() for s in t.spans]
    agent_spans = [s for s in all_spans if s.kind == SpanKind.AGENT]
    assert len(agent_spans) >= 1
    exec_span = next(s for s in agent_spans if s.name == "plan:execute")
    assert exec_span.status == SpanStatus.OK


def test_execute_failed_plan_span_has_error_status():
    """T8b: A failed plan sets the execute span to ERROR status."""
    provider = FakeProvider("p", [RuntimeError("failure")])
    router = Router(
        RoutingPolicy([Candidate(provider, "fake")], max_retries=0),
        export_hook=None,
    )
    plan = Plan(goal="fail trace", steps=[Step(description="bad step")])
    asyncio.run(execute(plan, _empty_dispatcher(), router, max_replan=0))

    collector = get_collector()
    all_spans = [s for t in collector.all_traces() for s in t.spans]
    exec_span = next(
        s for s in all_spans if s.name == "plan:execute" and s.kind == SpanKind.AGENT
    )
    assert exec_span.status == SpanStatus.ERROR


# ---------------------------------------------------------------------------
# T9: memory context injection
# ---------------------------------------------------------------------------


def test_execute_llm_step_with_memory():
    """T9: Memory items are injected into the LLM prompt for LLM steps."""
    from llm_agents.core.agent_memory._models import MemoryItem
    from llm_agents.core.agent_memory._short_term import ShortTermMemory

    # Use a provider that captures the request for inspection
    captured_requests: list = []

    class CapturingProvider:
        name = "capturing"

        async def complete(self, request):
            captured_requests.append(request)
            return _fake_response("captured answer")

    provider = CapturingProvider()
    policy = RoutingPolicy([Candidate(provider=provider, model="test")])
    router = Router(policy, export_hook=None)

    memory = ShortTermMemory()
    memory.add(MemoryItem(content="prior context line", role="assistant", timestamp=0.0))

    step = Step(description="what was said?", tool_arguments={"model": "test"})
    plan = Plan(goal="recall", steps=[step])

    asyncio.run(execute(plan, _empty_dispatcher(), router, memory=memory))

    assert captured_requests, "Provider was not called"
    prompt_content = captured_requests[0].messages[0]["content"]
    assert "prior context line" in prompt_content
