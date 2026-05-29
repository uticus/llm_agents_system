"""GuardrailChain: run a sequence of guards in order.

:class:`GuardrailChain` applies guards left-to-right.  The chain stops at the
first BLOCK or REDACT result and returns it; if all guards pass, a PASS result
is returned.  An optional ``on_violation`` callback is invoked for audit
logging whenever a guard does not pass.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from llm_agents.infra.guardrails._models import GuardAction, GuardResult


class GuardrailChain:
    """Applies a sequence of :class:`Guard`-compatible objects to text.

    Args:
        guards:       Ordered list of guard objects.  Each must implement
                      ``check(text: str) -> GuardResult``.
        on_violation: Optional callback ``(result: GuardResult) -> None``
                      invoked whenever a guard does not pass (BLOCK or
                      REDACT).  Useful for audit logging.
    """

    def __init__(
        self,
        guards: list[Any],
        on_violation: Callable[[GuardResult], None] | None = None,
    ) -> None:
        self._guards = guards
        self._on_violation = on_violation

    def run(self, text: str) -> GuardResult:
        """Run all guards on *text* in order.

        Stops immediately when any guard returns BLOCK or REDACT.

        Args:
            text: The text to validate (input or output).

        Returns:
            The first non-passing :class:`GuardResult`, or a passing
            result if all guards pass.
        """
        current_text = text
        for guard in self._guards:
            result = guard.check(current_text)
            if result.action in (GuardAction.BLOCK, GuardAction.REDACT):
                if self._on_violation is not None:
                    self._on_violation(result)
                return result
            # PASS — continue with (possibly updated) text
            current_text = result.text

        return GuardResult.pass_(current_text)
