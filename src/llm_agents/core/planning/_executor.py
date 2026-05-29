"""Plan executor: drives step-by-step execution with replanning on failure.

:func:`execute` iterates a :class:`Plan` step by step.  Each step is either
dispatched as a tool call (when :attr:`Step.tool_name` is set) or answered
via an LLM router call.  Failed steps trigger one replanning attempt using the
provided :class:`Planner`; if replanning is unavailable or also fails, the
step is marked :attr:`StepStatus.FAILED` and the plan halts.

A :data:`SpanKind.AGENT` tracing span is emitted for each :func:`execute`
invocation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from llm_agents.core.planning._models import Plan, PlanStatus, Step, StepStatus
from llm_agents.infra.tracing import tracer
from llm_agents.infra.tracing._models import SpanKind, SpanStatus

if TYPE_CHECKING:
    from llm_agents.core.agent_memory._short_term import ShortTermMemory
    from llm_agents.core.planning._planner import Planner
    from llm_agents.core.tool_orchestration._dispatcher import ToolDispatcher


async def execute(
    plan: Plan,
    dispatcher: ToolDispatcher,
    router: Any,
    memory: ShortTermMemory | None = None,
    planner: Planner | None = None,
    max_replan: int = 1,
) -> Plan:
    """Execute *plan* step by step, replanning on failure.

    Steps are executed in order.  For each step:

    1. Mark the step :attr:`StepStatus.RUNNING`.
    2. Dispatch as a tool call if :attr:`Step.tool_name` is set, otherwise
       call *router* with the step description as the user prompt.
    3. On success — mark :attr:`StepStatus.DONE` and store the result.
    4. On failure — if *planner* is provided and *max_replan* > 0, replace the
       failed step with the steps produced by replanning (limited to one
       replanning per original step) and retry the new steps.  If replanning
       is unavailable or also fails, mark the step :attr:`StepStatus.FAILED`,
       set the plan to :attr:`PlanStatus.FAILED`, and stop.

    A :data:`SpanKind.AGENT` tracing span wraps the entire call.

    Args:
        plan:        The :class:`Plan` to execute (mutated in place).
        dispatcher:  :class:`ToolDispatcher` used for tool steps.
        router:      Object with ``complete(LLMRequest) -> LLMResponse`` for
                     LLM steps.  Accepts :class:`Router` or any compatible stub.
        memory:      Optional :class:`ShortTermMemory` whose recent items are
                     concatenated into the LLM prompt as context.
        planner:     Optional :class:`Planner` used for replanning on failure.
        max_replan:  Maximum number of replanning attempts across the whole
                     execution.  Defaults to 1.

    Returns:
        The (mutated) *plan* with updated step and plan statuses.
    """
    async with tracer.span(
        "plan:execute",
        kind=SpanKind.AGENT,
        goal=plan.goal,
        step_count=len(plan.steps),
    ) as span:
        plan.status = PlanStatus.RUNNING
        replan_budget = max_replan

        i = 0
        while i < len(plan.steps):
            step = plan.steps[i]
            step.status = StepStatus.RUNNING

            error = await _run_step(step, dispatcher, router, memory)

            if error is None:
                step.status = StepStatus.DONE
                i += 1
                continue

            # Step failed — attempt replanning
            step.status = StepStatus.FAILED
            step.error = error

            if planner is not None and replan_budget > 0:
                replan_budget -= 1
                try:
                    new_plan = await planner.plan(step.description)
                except Exception as exc:  # noqa: BLE001
                    # Replanning itself failed — halt
                    plan.status = PlanStatus.FAILED
                    span.status = SpanStatus.ERROR
                    span.attributes["error"] = f"Replanning failed: {exc}"
                    return plan

                # Replace the failed step with the new steps
                plan.steps[i : i + 1] = new_plan.steps

                # Retry from the same index position (now pointing at new steps)
                continue

            # No planner or budget exhausted — halt
            plan.status = PlanStatus.FAILED
            span.status = SpanStatus.ERROR
            span.attributes["error"] = f"Step '{step.description}' failed: {error}"
            return plan

        plan.status = PlanStatus.DONE
        span.status = SpanStatus.OK
        return plan


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _run_step(
    step: Step,
    dispatcher: ToolDispatcher,
    router: Any,
    memory: ShortTermMemory | None,
) -> str | None:
    """Execute a single step; return ``None`` on success or an error string.

    Args:
        step:       The step to execute.
        dispatcher: Tool dispatcher for tool steps.
        router:     LLM router for inference steps.
        memory:     Optional short-term memory for context injection.

    Returns:
        ``None`` on success (step.result is populated).
        A human-readable error string on failure.
    """
    if step.tool_name is not None:
        return await _run_tool_step(step, dispatcher)
    return await _run_llm_step(step, router, memory)


async def _run_tool_step(step: Step, dispatcher: ToolDispatcher) -> str | None:
    """Dispatch *step* as a tool call.

    Args:
        step:       Step with :attr:`Step.tool_name` set.
        dispatcher: ToolDispatcher to invoke.

    Returns:
        ``None`` on success; error string on failure.
    """
    from llm_agents.core.tool_orchestration._models import ToolCall

    call = ToolCall(
        name=step.tool_name,  # type: ignore[arg-type]
        arguments=step.tool_arguments,
        call_id=step.id,
    )
    result = await dispatcher.dispatch(call)
    if result.success:
        step.result = result.output
        return None
    return result.error


async def _run_llm_step(
    step: Step,
    router: Any,
    memory: ShortTermMemory | None,
) -> str | None:
    """Answer *step* via an LLM router call.

    Prepends recent memory items as context when *memory* is provided.

    Args:
        step:   Step without :attr:`Step.tool_name` (LLM-answered).
        router: LLM router with ``complete(LLMRequest) -> LLMResponse``.
        memory: Optional short-term memory for context injection.

    Returns:
        ``None`` on success; error string on failure.
    """
    from llm_agents.infra.inference_routing._models import LLMRequest

    context_lines: list[str] = []
    if memory is not None:
        for item in memory.items():
            context_lines.append(f"[{item.role}]: {item.content}")

    prompt_parts = []
    if context_lines:
        prompt_parts.append("Context:\n" + "\n".join(context_lines))
    prompt_parts.append(step.description)
    prompt = "\n\n".join(prompt_parts)

    model = step.tool_arguments.get("model", "default")
    request = LLMRequest(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        response = await router.complete(request)
        step.result = response.content
        return None
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"
