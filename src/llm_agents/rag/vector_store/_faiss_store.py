"""FAISSVectorStore — FAISS-backed implementation of the VectorStore Protocol.

Uses a flat inner-product index (``faiss.IndexFlatIP``).  Vectors are
L2-normalised before insertion so that inner-product search is equivalent
to cosine-similarity ranking.

The index is rebuilt lazily: any ``upsert`` or ``delete`` marks the index as
dirty; the next ``search`` call triggers a rebuild from ``_data`` before
querying.  This is O(n) per rebuild but correct at all times and suitable
for corpora up to ~100 k vectors.

``import faiss`` and ``import numpy`` are **deferred** to the first
``_build_index`` call so that importing this module without the ``rag``
extra installed does not raise an ``ImportError``.
"""

from __future__ import annotations

from typing import Any

from llm_agents.rag.vector_store._store import SearchResult


class FAISSVectorStore:
    """FAISS-backed vector store using a flat inner-product index.

    Vectors are L2-normalised on insertion; inner-product search is therefore
    equivalent to cosine-similarity ranking.

    Args:
        dimensions: Embedding dimensionality.  If *None* (default), the value
                    is inferred from the first :meth:`upsert` call.  All
                    subsequent vectors must have the same length.

    Example::

        store = FAISSVectorStore()
        store.upsert("doc1", [0.1, 0.9], {"text": "hello"})
        results = store.search([0.1, 0.9], top_k=1)
    """

    def __init__(self, dimensions: int | None = None) -> None:
        self._dimensions: int | None = dimensions
        # Source of truth: doc_id -> (raw_vector, metadata)
        self._data: dict[str, tuple[list[float], dict[str, Any]]] = {}
        # Ordered list of doc_ids matching the FAISS index rows
        self._id_list: list[str] = []
        # FAISS index (Any to avoid importing faiss at class-definition time)
        self._index: Any = None
        # True whenever _data has changed since the last index build
        self._dirty: bool = False

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def upsert(
        self,
        doc_id: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or update the vector for *doc_id*.

        Args:
            doc_id:   Unique identifier.
            vector:   Embedding vector.  Length must match all previous upserts.
            metadata: Optional metadata stored alongside the vector.

        Raises:
            ValueError: If *vector* length does not match the store's
                        established dimensionality.
        """
        if self._dimensions is None:
            self._dimensions = len(vector)
        elif len(vector) != self._dimensions:
            raise ValueError(
                f"Vector length {len(vector)} does not match "
                f"store dimensionality {self._dimensions}."
            )
        self._data[doc_id] = (list(vector), dict(metadata) if metadata else {})
        self._dirty = True

    def delete(self, doc_id: str) -> bool:
        """Remove the entry for *doc_id*.

        Returns:
            ``True`` if the entry existed and was removed; ``False`` otherwise.
        """
        if doc_id not in self._data:
            return False
        del self._data[doc_id]
        self._dirty = True
        return True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Return the *top_k* entries with the highest cosine similarity.

        The index is rebuilt from ``_data`` if any mutation occurred since
        the last search.

        Args:
            query_vector: Query embedding vector.
            top_k:        Maximum number of results to return.

        Returns:
            List of :class:`SearchResult` sorted by descending score.
        """
        if self._dirty or self._index is None:
            self._build_index()
        if not self._id_list or self._index is None:
            return []

        import numpy as np  # noqa: PLC0415

        k = min(top_k, len(self._id_list))
        q = np.array([query_vector], dtype=np.float32)
        import faiss as _faiss  # noqa: PLC0415

        _faiss.normalize_L2(q)
        scores, indices = self._index.search(q, k)

        results: list[SearchResult] = []
        for score, idx in zip(scores[0], indices[0], strict=True):
            if idx < 0:
                continue
            did = self._id_list[int(idx)]
            _, meta = self._data[did]
            results.append(
                SearchResult(
                    doc_id=did,
                    score=float(score),
                    metadata=dict(meta),
                )
            )
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_index(self) -> None:
        """Rebuild the FAISS index from the current contents of ``_data``."""
        import faiss  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        self._id_list = list(self._data.keys())
        if not self._id_list or self._dimensions is None:
            self._index = None
            self._dirty = False
            return

        vecs = np.array(
            [self._data[did][0] for did in self._id_list],
            dtype=np.float32,
        )
        faiss.normalize_L2(vecs)
        index = faiss.IndexFlatIP(self._dimensions)
        index.add(vecs)
        self._index = index
        self._dirty = False

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, doc_id: str) -> bool:
        return doc_id in self._data
