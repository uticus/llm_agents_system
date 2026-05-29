"""Built-in evaluation metrics.

:class:`Metric` is a structural ``Protocol`` — any callable-like object with a
matching ``score(expected, actual) -> float`` method qualifies.

Built-in implementations:

- :class:`ExactMatchMetric` — 1.0 iff *actual* equals *expected* (case-sensitive).
- :class:`ContainsMetric` — 1.0 iff *expected* is a substring of *actual*
  (case-insensitive).
- :class:`NormalizedMatchMetric` — case-insensitive, strip-whitespace equality.
"""

from __future__ import annotations

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable


@runtime_checkable
class Metric(Protocol):
    """Protocol for evaluation metrics.

    Any object with a matching ``score`` method satisfies this interface
    without needing to inherit from :class:`Metric`.
    """

    def score(self, expected: str, actual: str) -> float:
        """Return a score in ``[0.0, 1.0]`` comparing *actual* to *expected*.

        Args:
            expected: The expected/reference output.
            actual:   The agent-produced output to evaluate.

        Returns:
            A float in ``[0.0, 1.0]``.  1.0 = perfect match.
        """
        ...


class ExactMatchMetric:
    """Returns 1.0 iff *actual* exactly equals *expected* (case-sensitive)."""

    def score(self, expected: str, actual: str) -> float:
        """Score: 1.0 on exact match, 0.0 otherwise."""
        return 1.0 if actual == expected else 0.0


class ContainsMetric:
    """Returns 1.0 iff *expected* is a substring of *actual* (case-insensitive)."""

    def score(self, expected: str, actual: str) -> float:
        """Score: 1.0 if *expected* appears anywhere in *actual*."""
        return 1.0 if expected.lower() in actual.lower() else 0.0


class NormalizedMatchMetric:
    """Returns 1.0 iff *actual* equals *expected* after lowercasing and stripping."""

    def score(self, expected: str, actual: str) -> float:
        """Score: 1.0 if normalized strings are equal."""
        return 1.0 if actual.strip().lower() == expected.strip().lower() else 0.0
