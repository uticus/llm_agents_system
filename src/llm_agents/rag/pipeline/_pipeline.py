"""RagPipeline: retrieve -> (optional rerank) -> generate grounded answer.

:class:`GroundedAnswer` carries the generated text and the cited passages so
callers can inspect the evidence used to produce the answer.

:class:`RagPipeline` composes a retriever, an optional reranker, and a
generator callable into a single ``answer()`` entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llm_agents.rag.retrieval._retriever import RetrievedPassage

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class GroundedAnswer:
    """The result of a RAG pipeline run.

    Attributes:
        query:     The original query text.
        answer:    Generated answer string.
        citations: Passages used to ground the answer (in retrieval order).
    """

    query: str
    answer: str
    citations: list[RetrievedPassage] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class RagPipeline:
    """Retrieve -> rerank -> generate pipeline.

    Args:
        retriever: Any object with a ``retrieve(query, ...)`` method compatible
                   with :class:`~llm_agents.rag.retrieval.DenseRetriever`.
        generator: Callable ``(query: str, passages: list[RetrievedPassage]) -> str``
                   that generates the grounded answer from retrieved context.
        reranker:  Optional reranker applied after retrieval.  When ``None``
                   the retrieved passages are used as-is.
        top_k:     Number of passages to retrieve (default 5).
        top_n:     Maximum passages to pass to the generator after reranking
                   (default equals *top_k*; ignored when reranker is ``None``).
    """

    def __init__(
        self,
        retriever: Any,
        generator: Any,
        *,
        reranker: Any = None,
        top_k: int = 5,
        top_n: int | None = None,
    ) -> None:
        self._retriever = retriever
        self._generator = generator
        self._reranker = reranker
        self.top_k = top_k
        self.top_n = top_n

    def answer(
        self,
        query: str,
        *,
        top_k: int | None = None,
        top_n: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> GroundedAnswer:
        """Retrieve, rerank, and generate a grounded answer for *query*.

        Args:
            query:   User question.
            top_k:   Override retrieval count for this call.
            top_n:   Override reranking truncation for this call.
            filters: Metadata filters forwarded to the retriever.

        Returns:
            :class:`GroundedAnswer` with the generated text and cited passages.
        """
        k = top_k if top_k is not None else self.top_k
        n = top_n if top_n is not None else self.top_n

        # Retrieve
        passages: list[RetrievedPassage] = self._retriever.retrieve(
            query,
            top_k=k,
            filters=filters,
        )

        # Rerank (optional)
        if self._reranker is not None:
            passages = self._reranker.rerank(query, passages, top_n=n)

        # Generate
        answer_text: str = self._generator(query, passages)

        return GroundedAnswer(
            query=query,
            answer=answer_text,
            citations=passages,
        )
