"""Data models for the guardrails subsystem.

:class:`GuardAction` enumerates the possible outcomes of a guard check.
:class:`GuardResult` carries the full outcome including the (possibly
modified) text and a human-readable violation description.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GuardAction(StrEnum):
    """Terminal action of a guardrail check."""

    PASS = "pass"
    BLOCK = "block"
    REDACT = "redact"


@dataclass(frozen=True)
class GuardResult:
    """Outcome of a single :class:`Guard` check or a :class:`GuardrailChain` run.

    Args:
        passed:           ``True`` when the action is :attr:`GuardAction.PASS`.
        action:           The action taken by the guard.
        text:             The (possibly redacted) text after processing.
        violation_detail: Human-readable description of the violation, or
                          ``None`` when the check passed.
    """

    passed: bool
    action: GuardAction
    text: str
    violation_detail: str | None = None

    @classmethod
    def pass_(cls, text: str) -> GuardResult:
        """Convenience constructor for a passing result."""
        return cls(passed=True, action=GuardAction.PASS, text=text)

    @classmethod
    def block(cls, text: str, detail: str) -> GuardResult:
        """Convenience constructor for a blocking result."""
        return cls(passed=False, action=GuardAction.BLOCK, text=text, violation_detail=detail)

    @classmethod
    def redact(cls, text: str, detail: str) -> GuardResult:
        """Convenience constructor for a redacted result."""
        return cls(passed=False, action=GuardAction.REDACT, text=text, violation_detail=detail)
