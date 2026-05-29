"""Planner implementations: SequentialPlanner and LLMPlanner.

:class:`Planner` is a structural ``Protocol`` — any class with a matching
``plan(goal, context)`` coroutine qualifies without inheritance.

:class:`SequentialPlanner` is the trivial strategy: the entire goal becomes
one LLM-answered step.

:class:`LLMPlanner` decomposes the goal into multiple steps by asking the
router to produce a ``STEP: <description>`` list.  Each line that starts with
``STEP:`` becomes one :class:`Step` in the returned :class:`Plan`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from llm_agents.core.planning._models import Plan, Step

if TYPE_CHECKING:

    pass

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable

_DECOMPOSE_PROMPT = (
    "You are a planning assistant. Break the following goal into a numbered list of "
    "steps. Each step must begin with 'STEP: ' followed by a short action description. "
    "Output one step per line, nothing else.\n\nGoal: {goal}\n\nContext:\n{context}"
)


@runtime_checkable
class Planner(Protocol):
    """Protocol for goal-to-plan strategies.

    Any object with a matching ``plan`` coroutine satisfies this interface
    without needing to inherit from :class:`Planner`.
    """

    async def plan(self, goal: str, context: str = "") -> Plan:
        """Decompose *goal* into a :class:`Plan`.

        Args:
            goal:    The goal to plan for.
            context: Optional additional context (e.g. memory snapshot).

        Returns:
            A :class:`Plan` with ``status=PENDING`` and at least one step.
        """
        ...


class SequentialPlanner:
    """The simplest planner: wraps the entire goal in a single LLM step.

    No LLM call is made during :meth:`plan`; the returned :class:`Plan`
    contains one :class:`Step` that instructs the executor to call the
    router with the goal as the prompt.

    Args:
        model: Model name forwarded in the step's ``tool_arguments`` for use
               by the executor.  Defaults to ``"default"``.
    """

    def __init__(self, model: str = "default") -> None:
        self._model = model

    async def plan(self, goal: str, context: str = "") -> Plan:
        """Return a single-step plan for *goal*.

        Args:
            goal:    Goal string.
            context: Ignored by this planner.

        Returns:
            A :class:`Plan` containing exactly one :class:`Step`.
        """
        step = Step(
            description=goal,
            tool_name=None,
            tool_arguments={"model": self._model},
        )
        return Plan(goal=goal, steps=[step])


class LLMPlanner:
    """Goal-decomposition planner that calls an LLM to produce the step list.

    The router is called once with a prompt that asks for ``STEP: <text>``
    lines.  Lines in the response that do not start with ``STEP:`` are
    ignored.  If no ``STEP:`` lines are found, a single-step fallback plan is
    returned.

    Args:
        router: An object with an async ``complete(LLMRequest) -> LLMResponse``
                method.  Accepts :class:`Router` or any compatible stub.
        model:  Model name to send in the planning request.
    """

    def __init__(self, router: Any, model: str = "default") -> None:
        self._router = router
        self._model = model

    async def plan(self, goal: str, context: str = "") -> Plan:
        """Ask the router to decompose *goal* and parse the result.

        Args:
            goal:    Goal string.
            context: Optional context injected into the planning prompt.

        Returns:
            A :class:`Plan` with one :class:`Step` per ``STEP:`` line in the
            LLM response (or a single-step fallback if none are found).
        """
        from llm_agents.infra.inference_routing._models import LLMRequest

        prompt = _DECOMPOSE_PROMPT.format(goal=goal, context=context or "(none)")
        request = LLMRequest(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        response = await self._router.complete(request)
        steps = _parse_steps(response.content)
        if not steps:
            steps = [Step(description=goal)]
        return Plan(goal=goal, steps=steps)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_steps(text: str) -> list[Step]:
    """Parse ``STEP: <description>`` lines from *text*.

    Lines that do not begin with ``STEP:`` (case-insensitive) are ignored.
    Returns an empty list if no matching lines are found.

    Args:
        text: Raw LLM response text.

    Returns:
        Ordered list of :class:`Step` objects, one per ``STEP:`` line.
    """
    steps: list[Step] = []
    for line in text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("STEP:"):
            description = stripped[len("STEP:"):].strip()
            if description:
                steps.append(Step(description=description))
    return steps
