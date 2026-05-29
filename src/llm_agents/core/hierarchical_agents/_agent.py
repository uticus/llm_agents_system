"""Agent protocol and Worker implementation.

:class:`Agent` is a structural ``Protocol`` — any class with a matching
``run(task)`` coroutine qualifies without inheritance.

:class:`Worker` is a concrete implementation that answers a task string via
an LLM router call.  Optionally, it can dispatch a named tool via a
:class:`ToolDispatcher` when ``tool_name`` is supplied at construction time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from llm_agents.core.hierarchical_agents._models import AgentResult

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable

if TYPE_CHECKING:
    from llm_agents.core.tool_orchestration._dispatcher import ToolDispatcher


@runtime_checkable
class Agent(Protocol):
    """Protocol for agent implementations.

    Any object with a matching ``run`` coroutine satisfies this interface
    without needing to inherit from :class:`Agent`.
    """

    async def run(self, task: str) -> AgentResult:
        """Execute *task* and return an :class:`AgentResult`.

        Args:
            task: Natural-language task description.

        Returns:
            :class:`AgentResult` — always, never raises.
        """
        ...


class Worker:
    """Concrete agent that answers a task string via an LLM router call.

    If *tool_name* is set and a :class:`ToolDispatcher` is provided, the
    worker dispatches a tool call instead of a plain LLM call.  The task
    string is passed as a ``"query"`` argument to the tool.

    Args:
        router:     LLM router with ``complete(LLMRequest) -> LLMResponse``.
        model:      Model name to use for LLM calls.  Defaults to ``"default"``.
        dispatcher: Optional :class:`ToolDispatcher` for tool-based tasks.
        tool_name:  If set, dispatch this tool instead of calling the LLM.
    """

    def __init__(
        self,
        router: Any,
        model: str = "default",
        dispatcher: ToolDispatcher | None = None,
        tool_name: str | None = None,
    ) -> None:
        self._router = router
        self._model = model
        self._dispatcher = dispatcher
        self._tool_name = tool_name

    async def run(self, task: str) -> AgentResult:
        """Execute *task* and return an :class:`AgentResult`.

        Args:
            task: Natural-language task description or query string.

        Returns:
            :class:`AgentResult` — always, never raises.
        """
        if self._tool_name and self._dispatcher is not None:
            return await self._run_tool(task)
        return await self._run_llm(task)

    async def _run_llm(self, task: str) -> AgentResult:
        from llm_agents.infra.inference_routing._models import LLMRequest

        request = LLMRequest(
            model=self._model,
            messages=[{"role": "user", "content": task}],
        )
        try:
            response = await self._router.complete(request)
            return AgentResult.ok(task=task, output=response.content)
        except Exception as exc:  # noqa: BLE001
            return AgentResult.err(task=task, error=f"{type(exc).__name__}: {exc}")

    async def _run_tool(self, task: str) -> AgentResult:
        from llm_agents.core.tool_orchestration._models import ToolCall

        assert self._dispatcher is not None  # guaranteed by caller
        call = ToolCall(
            name=self._tool_name,  # type: ignore[arg-type]
            arguments={"query": task},
        )
        result = await self._dispatcher.dispatch(call)
        if result.success:
            return AgentResult.ok(task=task, output=result.output)
        return AgentResult.err(task=task, error=result.error or "Tool failed")
