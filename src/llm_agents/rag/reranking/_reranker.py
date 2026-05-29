"""Reranker protocol and FakeReranker implementation.

:class:`Reranker` is a structural ``Protocol`` — any class with a matching
``rerank`` method qualifies.

:class:`FakeReranker` reverses the input list (deterministic, no model
calls) and optionally truncates to *top_n* for tests.
"""

from __future__ import annotations

from typing import Any

from llm_agents.rag.retrieval._retriever import RetrievedPassage

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable


@runtime_checkable
class Reranker(Protocol):
    """Protocol for passage rerankers.

    Any object with a matching ``rerank`` method satisfies this interface
    without needing to inherit from :class:`Reranker`.
    """

    def rerank(
        self,
        query: str,
        passages: list[RetrievedPassage],
        *,
        top_n: int | None = None,
    ) -> list[RetrievedPassage]:
        """Rerank *passages* by relevance to *query*.

        Args:
            query:    Query text used to score passages.
            passages: Candidate passages, typically from a retriever.
            top_n:    If set, truncate the result to the best *top_n* passages.

        Returns:
            Reranked (and optionally truncated) list of passages.
        """
        ...


class FakeReranker:
    """Deterministic test reranker that reverses the passage list.

    The reversed order is predictable without any model calls, making it
    easy to verify that the reranker was invoked in tests.

    Args:
        top_n: Default number of passages to keep.  ``None`` means keep all.

    Attributes:
        rerank_count: Number of ``rerank`` calls made so far.
    """

    def __init__(self, top_n: int | None = None) -> None:
        self.top_n = top_n
        self.rerank_count = 0

    def rerank(
        self,
        query: str,
        passages: list[RetrievedPassage],
        *,
        top_n: int | None = None,
    ) -> list[RetrievedPassage]:
        """Return passages in reversed order, optionally truncated.

        Args:
            query:    Ignored (deterministic fake).
            passages: Passages to rerank.
            top_n:    Overrides constructor *top_n* when provided.

        Returns:
            Reversed list, truncated to *top_n* if set.
        """
        self.rerank_count += 1
        n = top_n if top_n is not None else self.top_n
        result = list(reversed(passages))
        if n is not None:
            result = result[:n]
        return result


class ScoreReranker:
    """Reranker that sorts passages by a caller-supplied scorer.

    Args:
        scorer: Callable ``(query: str, passage: RetrievedPassage) -> float``.
                Higher scores rank higher.
        top_n:  Default number of passages to keep.

    Attributes:
        rerank_count: Number of ``rerank`` calls.
    """

    def __init__(
        self,
        scorer: Any,
        top_n: int | None = None,
    ) -> None:
        self._scorer = scorer
        self.top_n = top_n
        self.rerank_count = 0

    def rerank(
        self,
        query: str,
        passages: list[RetrievedPassage],
        *,
        top_n: int | None = None,
    ) -> list[RetrievedPassage]:
        """Sort *passages* by score descending, optionally truncate.

        Args:
            query:    Passed to the scorer.
            passages: Candidate passages.
            top_n:    Overrides constructor *top_n* when provided.

        Returns:
            Passages sorted by descending scorer output.
        """
        self.rerank_count += 1
        n = top_n if top_n is not None else self.top_n
        scored = sorted(
            passages,
            key=lambda p: self._scorer(query, p),
            reverse=True,
        )
        if n is not None:
            scored = scored[:n]
        return scored
