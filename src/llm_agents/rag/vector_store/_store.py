"""VectorStore protocol and InMemoryVectorStore implementation.

:class:`VectorStore` is a structural ``Protocol`` — any class with matching
``upsert``, ``search``, and ``delete`` members qualifies.

:class:`InMemoryVectorStore` stores vectors in a Python dict and performs
brute-force cosine-similarity search.  For tests and prototyping only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    """A single result from a vector-store search.

    Attributes:
        doc_id:   Identifier of the stored vector.
        score:    Cosine similarity in ``[-1.0, 1.0]`` (higher is better).
        metadata: Arbitrary key-value metadata attached at upsert time.
    """

    doc_id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector stores.

    Any object with matching ``upsert``, ``search``, and ``delete`` members
    satisfies this interface without needing to inherit from
    :class:`VectorStore`.
    """

    def upsert(
        self,
        doc_id: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or update a vector entry.

        Args:
            doc_id:   Unique identifier.
            vector:   Embedding vector.
            metadata: Optional metadata to store alongside the vector.
        """
        ...

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Return the *top_k* most similar stored vectors.

        Args:
            query_vector: Query embedding vector.
            top_k:        Maximum number of results to return.

        Returns:
            List of :class:`SearchResult` sorted by descending score.
        """
        ...

    def delete(self, doc_id: str) -> bool:
        """Remove a stored vector by its identifier.

        Args:
            doc_id: Identifier to remove.

        Returns:
            ``True`` if the entry existed and was removed; ``False`` otherwise.
        """
        ...


# ---------------------------------------------------------------------------
# InMemoryVectorStore
# ---------------------------------------------------------------------------


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class _Entry:
    vector: list[float]
    metadata: dict[str, Any]


class InMemoryVectorStore:
    """Brute-force in-memory vector store.

    Vectors are stored in a plain dict keyed by ``doc_id``.  Search computes
    cosine similarity against every stored vector (O(n) per query).

    Suitable for tests and small-scale prototyping only.
    """

    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def upsert(
        self,
        doc_id: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or replace the vector for *doc_id*.

        Args:
            doc_id:   Unique identifier.
            vector:   Embedding vector (any length > 0).
            metadata: Optional metadata; copied on write.
        """
        self._store[doc_id] = _Entry(
            vector=list(vector),
            metadata=dict(metadata) if metadata else {},
        )

    def delete(self, doc_id: str) -> bool:
        """Remove the entry for *doc_id*.

        Returns:
            ``True`` if the entry was present and removed.
        """
        if doc_id in self._store:
            del self._store[doc_id]
            return True
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Return the *top_k* entries with the highest cosine similarity.

        Args:
            query_vector: Query embedding vector.
            top_k:        Maximum number of results (clamped to store size).

        Returns:
            List of :class:`SearchResult` sorted by descending score.
        """
        scored = [
            SearchResult(
                doc_id=doc_id,
                score=_cosine(query_vector, entry.vector),
                metadata=dict(entry.metadata),
            )
            for doc_id, entry in self._store.items()
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, doc_id: str) -> bool:
        return doc_id in self._store
