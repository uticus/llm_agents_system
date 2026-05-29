"""Budget tracking for LLM call costs and token usage.

:class:`BudgetTracker` accumulates token counts and cost across multiple
:class:`~llm_agents.infra.inference_routing.LLMResponse` objects and exposes
a :class:`BudgetReport` snapshot on demand.

Usage::

    tracker = BudgetTracker()
    response = await router.complete(request)
    tracker.track(response)
    report = tracker.report()
    print(f"Total cost so far: ${report.cost_usd:.6f}")
"""

from __future__ import annotations

from dataclasses import dataclass

from llm_agents.infra.inference_routing._models import LLMResponse


@dataclass(frozen=True)
class BudgetReport:
    """Immutable snapshot of accumulated usage for a :class:`BudgetTracker`.

    Args:
        prompt_tokens:     Total prompt tokens across all tracked calls.
        completion_tokens: Total completion tokens across all tracked calls.
        total_tokens:      ``prompt_tokens + completion_tokens``.
        cost_usd:          Accumulated estimated cost in USD.
        call_count:        Number of :class:`LLMResponse` objects tracked.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    call_count: int


class BudgetTracker:
    """Accumulates token counts and cost from LLM responses.

    Not thread-safe; intended for use within a single asyncio task.
    Call :meth:`reset` to start a new tracking period.
    """

    def __init__(self) -> None:
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0
        self._cost_usd: float = 0.0
        self._call_count: int = 0

    def track(self, response: LLMResponse) -> None:
        """Record the usage figures from *response*.

        Args:
            response: Finished LLM response to account for.
        """
        self._prompt_tokens += response.prompt_tokens
        self._completion_tokens += response.completion_tokens
        self._cost_usd += response.cost_usd
        self._call_count += 1

    def report(self) -> BudgetReport:
        """Return a snapshot of accumulated usage figures."""
        return BudgetReport(
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            total_tokens=self._prompt_tokens + self._completion_tokens,
            cost_usd=self._cost_usd,
            call_count=self._call_count,
        )

    def reset(self) -> None:
        """Reset all accumulators to zero."""
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._cost_usd = 0.0
        self._call_count = 0
