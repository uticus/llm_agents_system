"""Built-in guard implementations.

:class:`Guard` is a structural ``Protocol`` — any object with a ``check``
method matching the signature qualifies.

Built-in guards:

- :class:`RegexFilter` — blocks text that matches any of the supplied patterns.
- :class:`KeywordFilter` — blocks text that contains any listed keyword
  (case-insensitive).
- :class:`EmbeddingFilter` — blocks text when a provided scorer function
  returns a similarity below a threshold.
- :class:`RedactFilter` — replaces matched patterns with a redaction marker
  instead of blocking.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from llm_agents.infra.guardrails._models import GuardResult

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable

_REDACTION_MARKER = "[REDACTED]"


@runtime_checkable
class Guard(Protocol):
    """Protocol for guardrail checks.

    Any object with a matching ``check`` method satisfies this interface
    without needing to inherit from :class:`Guard`.
    """

    def check(self, text: str) -> GuardResult:
        """Evaluate *text* and return a :class:`GuardResult`.

        Args:
            text: The input or output text to validate.

        Returns:
            :class:`GuardResult` — always, never raises.
        """
        ...


class RegexFilter:
    """Blocks text that matches any of the supplied regex patterns.

    Args:
        patterns:  List of regex pattern strings.  Compiled at construction.
        flags:     ``re`` flags applied to all patterns (default 0).
        detail:    Template for the violation detail message.  ``{match}``
                   is replaced with the matched string.
    """

    def __init__(
        self,
        patterns: list[str],
        flags: int = 0,
        detail: str = "Blocked pattern matched: {match}",
    ) -> None:
        self._compiled = [re.compile(p, flags) for p in patterns]
        self._detail = detail

    def check(self, text: str) -> GuardResult:
        """Return BLOCK if any pattern matches, PASS otherwise."""
        for pattern in self._compiled:
            m = pattern.search(text)
            if m:
                detail = self._detail.format(match=m.group())
                return GuardResult.block(text=text, detail=detail)
        return GuardResult.pass_(text)


class KeywordFilter:
    """Blocks text that contains any of the listed keywords (case-insensitive).

    Args:
        keywords: List of keyword strings to check for.
    """

    def __init__(self, keywords: list[str]) -> None:
        self._keywords = [kw.lower() for kw in keywords]

    def check(self, text: str) -> GuardResult:
        """Return BLOCK if any keyword appears in *text*."""
        lower = text.lower()
        for kw in self._keywords:
            if kw in lower:
                return GuardResult.block(
                    text=text,
                    detail=f"Blocked keyword found: '{kw}'",
                )
        return GuardResult.pass_(text)


class RedactFilter:
    """Replaces matched patterns with a redaction marker (REDACT action).

    Unlike :class:`RegexFilter`, this guard does not block — it returns
    the modified text with matches replaced by ``[REDACTED]``.

    Args:
        patterns:  List of regex pattern strings.
        flags:     ``re`` flags applied to all patterns (default ``re.IGNORECASE``).
        marker:    Replacement string.  Defaults to ``"[REDACTED]"``.
    """

    def __init__(
        self,
        patterns: list[str],
        flags: int = re.IGNORECASE,
        marker: str = _REDACTION_MARKER,
    ) -> None:
        self._compiled = [re.compile(p, flags) for p in patterns]
        self._marker = marker

    def check(self, text: str) -> GuardResult:
        """Replace matched substrings and return a REDACT result if any matched."""
        modified = text
        matched = False
        for pattern in self._compiled:
            new_text, n = pattern.subn(self._marker, modified)
            if n > 0:
                matched = True
                modified = new_text
        if matched:
            return GuardResult.redact(text=modified, detail="Sensitive content redacted.")
        return GuardResult.pass_(text)


class EmbeddingFilter:
    """Blocks text when its similarity to a reference is below a threshold.

    The ``scorer`` callable receives the text and returns a float in
    ``[0.0, 1.0]`` (1.0 = identical to reference domain).  This class does
    not perform any embedding computation itself — it delegates to the
    caller-provided function (a stub or a real embedder).

    Args:
        scorer:    ``(text: str) -> float`` callable.
        threshold: Minimum acceptable similarity.  Text scoring below this
                   is blocked.  Default 0.5.
    """

    def __init__(
        self,
        scorer: Callable[[str], float],
        threshold: float = 0.5,
    ) -> None:
        self._scorer = scorer
        self._threshold = threshold

    def check(self, text: str) -> GuardResult:
        """Return BLOCK if scorer(text) < threshold, PASS otherwise."""
        score = self._scorer(text)
        if score < self._threshold:
            return GuardResult.block(
                text=text,
                detail=f"Embedding similarity {score:.3f} below threshold {self._threshold:.3f}",
            )
        return GuardResult.pass_(text)
