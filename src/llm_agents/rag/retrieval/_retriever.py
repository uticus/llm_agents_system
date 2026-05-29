"""DenseRetriever: embed query -> search vector store -> return passages.

:class:`RetrievedPassage` carries the matched text, score, and metadata.
:class:`DenseRetriever` wraps an embedder and a vector store and applies
optional metadata filters to post-filter search results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class RetrievedPassage:
    """A passage retrieved from the vector store.

    Attributes:
        doc_id:   Chunk identifier (as stored in the vector store).
        text:     The chunk text.  Empty string if not stored at index time.
        score:    Cosine similarity score from the vector store.
        metadata: Metadata attached to this chunk at index time.
    """

    doc_id: str
    text: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# DenseRetriever
# ---------------------------------------------------------------------------


class DenseRetriever:
    """Retrieve passages by dense (embedding-based) similarity search.

    Embeds the query text with *embedder*, queries *vector_store* for the
    *top_k* nearest vectors, and optionally post-filters results by metadata
    key-value pairs.

    Args:
        embedder:     Any object satisfying the
                      :class:`~llm_agents.rag.embeddings.Embedder` protocol.
        vector_store: Any object satisfying the
                      :class:`~llm_agents.rag.vector_store.VectorStore` protocol.
        top_k:        Default number of results to return (overridable per call).
    """

    def __init__(
        self,
        embedder: Any,
        vector_store: Any,
        top_k: int = 5,
    ) -> None:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        self._embedder = embedder
        self._vector_store = vector_store
        self.top_k = top_k

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedPassage]:
        """Retrieve the most relevant passages for *query*.

        Args:
            query:   Query text to embed and search.
            top_k:   Number of results (overrides constructor default when set).
            filters: Optional dict of ``{metadata_key: expected_value}``
                     pairs.  Only results where every key matches are kept.
                     Filtering is applied after score-based ranking so the
                     effective number of results may be less than *top_k*.

        Returns:
            List of :class:`RetrievedPassage` sorted by descending score.
        """
        k = top_k if top_k is not None else self.top_k
        vectors = self._embedder.embed([query])
        query_vector = vectors[0]

        raw = self._vector_store.search(query_vector, top_k=k)

        passages: list[RetrievedPassage] = []
        for result in raw:
            if filters and not _matches(result.metadata, filters):
                continue
            passages.append(
                RetrievedPassage(
                    doc_id=result.doc_id,
                    text=result.metadata.get("text", ""),
                    score=result.score,
                    metadata=dict(result.metadata),
                )
            )
        return passages


def _matches(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    return all(metadata.get(k) == v for k, v in filters.items())
