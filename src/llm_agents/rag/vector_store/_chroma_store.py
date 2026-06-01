"""ChromaVectorStore — Chroma-backed implementation of the VectorStore Protocol.

Uses the Chroma vector database (``chromadb>=0.5``) to store and query dense vectors.

Similarity metric: cosine similarity via Chroma's HNSW index configured with
``hnsw:space=cosine``.  Returned score = ``1.0 − cosine_distance``, so 1.0 = identical,
0.0 = orthogonal, and −1.0 = opposite directions.

The caller is responsible for providing an open Chroma client; the store does **not**
manage the client lifecycle.  Collection creation happens lazily on the first
:meth:`upsert` call (or an explicit call to :meth:`ensure_collection`).

Unlike the other adapters in this package, **no deferred import of** ``chromadb`` **is
needed** — all Chroma operations go through the injected client object, so this module
imports cleanly without the ``chroma`` extra installed.

Chroma's native ``collection.upsert`` provides atomic insert-or-replace semantics,
making the upsert implementation simpler than Weaviate (no check-then-branch needed).
"""

from __future__ import annotations

import re
from typing import Any

from llm_agents.rag.vector_store._store import SearchResult

# ---------------------------------------------------------------------------
# Collection name validation
# ---------------------------------------------------------------------------

# Mirrors Chroma's own validation rules:
#   - 3–63 characters
#   - starts and ends with an alphanumeric character
#   - middle may contain letters, digits, underscores, dots, and hyphens
#   - no consecutive dots
_SAFE_CHROMA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]$")


def _check_collection_name(name: str) -> str:
    """Validate a Chroma collection name; raise :class:`ValueError` on invalid values.

    Chroma enforces 3–63 characters, alphanumeric start/end, no consecutive dots,
    and no IP-address-shaped names.  This function checks the same rules, giving an
    early and descriptive error before the Chroma client is involved.

    Args:
        name: Candidate collection name.

    Returns:
        The name unchanged when it passes validation.

    Raises:
        ValueError: If ``name`` violates any Chroma naming rule.
    """
    if len(name) < 3:
        raise ValueError(
            f"Chroma collection name {name!r} must be at least 3 characters."
        )
    if len(name) > 63:
        raise ValueError(
            f"Chroma collection name {name!r} must be at most 63 characters."
        )
    if not _SAFE_CHROMA.match(name):
        raise ValueError(
            f"Invalid Chroma collection name {name!r}. "
            "Must start and end with an alphanumeric character and contain only "
            "ASCII letters, digits, underscores, dots, and hyphens."
        )
    if ".." in name:
        raise ValueError(
            f"Chroma collection name {name!r} must not contain consecutive dots."
        )
    return name


# ---------------------------------------------------------------------------
# ChromaVectorStore
# ---------------------------------------------------------------------------


class ChromaVectorStore:
    """Chroma-backed vector store using cosine similarity.

    Vectors are stored in a Chroma collection configured with an HNSW index and
    ``hnsw:space=cosine``.  Score returned = ``1.0 − cosine_distance`` (1.0 =
    identical, 0.0 = orthogonal, −1.0 = opposite directions).

    Chroma's native ``collection.upsert`` provides atomic insert-or-replace
    semantics — no existence check is needed before writing, unlike Weaviate.

    Args:
        client:          An open Chroma client (``chromadb.Client``,
                         ``chromadb.PersistentClient``, or any object with a
                         compatible ``get_or_create_collection`` method).  The
                         store does not manage the client lifecycle.
        collection_name: Name of the Chroma collection to use.  Must be 3–63
                         characters, start and end with an alphanumeric character,
                         and contain only letters, digits, underscores, dots, and
                         hyphens.  No consecutive dots.
        dimensions:      Embedding dimensionality.  If *None* (default), the value
                         is inferred from the first :meth:`upsert` call.  All
                         subsequent upserts must supply the same length.

    Raises:
        ValueError: At construction time if *collection_name* is invalid.

    Example::

        import chromadb
        client = chromadb.PersistentClient(path="/data/chroma")
        store = ChromaVectorStore(client, collection_name="rag_docs")
        store.upsert("doc1", embedding, {"source": "wiki"})
        results = store.search(query_vec, top_k=5)
    """

    def __init__(
        self,
        client: Any,
        collection_name: str = "llm_vectors",
        dimensions: int | None = None,
    ) -> None:
        self._client = client
        self._collection_name = _check_collection_name(collection_name)
        self._dimensions: int | None = dimensions
        self._collection: Any = None
        self._ready: bool = False

    # ------------------------------------------------------------------
    # Collection setup
    # ------------------------------------------------------------------

    def _ensure_collection(self) -> None:
        """Get or create the Chroma collection with ``hnsw:space=cosine``.

        Idempotent — if the collection already exists, it is returned unchanged.
        No ``import chromadb`` is needed; all calls go through the injected client.
        """
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._ready = True

    def ensure_collection(self) -> None:
        """Explicitly get or create the Chroma collection.

        Called automatically on the first :meth:`upsert`.  Call this method
        directly to initialise the store before querying a pre-existing collection
        without needing to upsert first.
        """
        self._ensure_collection()

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

        Uses Chroma's native ``collection.upsert`` for atomic insert-or-replace
        behaviour.  On the first call, the collection is created if it does not
        yet exist (see :meth:`_ensure_collection`).

        Args:
            doc_id:   Unique document identifier (used directly as the Chroma ID).
            vector:   Embedding vector.  Length must match established dimensionality.
            metadata: Optional key-value metadata stored as a Chroma metadata dict.
                      The dict is copied; caller mutations after this call do not
                      affect stored state.

        Raises:
            ValueError: If *vector* length does not match the store's established
                        dimensionality.
        """
        if self._dimensions is None:
            self._dimensions = len(vector)
        elif len(vector) != self._dimensions:
            raise ValueError(
                f"Vector length {len(vector)} does not match "
                f"store dimensionality {self._dimensions}."
            )
        if not self._ready:
            self._ensure_collection()
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[vector],
            metadatas=[dict(metadata) if metadata else {}],
        )

    def delete(self, doc_id: str) -> bool:
        """Remove the entry for *doc_id*.

        Returns:
            ``True`` if the entry existed and was removed; ``False`` otherwise.
            Always returns ``False`` before the first :meth:`upsert` call or
            :meth:`ensure_collection` call.
        """
        if not self._ready:
            return False
        result = self._collection.get(ids=[doc_id], include=[])
        if not result["ids"]:
            return False
        self._collection.delete(ids=[doc_id])
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

        Score is computed as ``1.0 − cosine_distance``, matching the range expected
        by the :class:`VectorStore` protocol.

        Chroma raises if ``n_results`` exceeds the number of stored items, so this
        method clamps to ``min(top_k, collection.count())``.  Returns an empty list
        if the collection is empty or not yet initialised.

        Args:
            query_vector: Query embedding vector.
            top_k:        Maximum number of results to return.

        Returns:
            List of :class:`SearchResult` sorted by descending score (Chroma returns
            results in ascending distance order, so the list is already in descending
            similarity order).
        """
        if not self._ready:
            return []
        count = self._collection.count()
        if count == 0:
            return []
        n = min(top_k, count)
        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=n,
            include=["distances", "metadatas"],
        )
        return [
            SearchResult(
                doc_id=doc_id,
                score=1.0 - float(distance),
                metadata=dict(meta) if meta else {},
            )
            for doc_id, distance, meta in zip(
                results["ids"][0],
                results["distances"][0],
                results["metadatas"][0],
                strict=True,
            )
        ]

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of stored vectors via ``collection.count()``.

        Returns 0 before :meth:`upsert` or :meth:`ensure_collection` is called.
        """
        if not self._ready:
            return 0
        return self._collection.count()

    def __contains__(self, doc_id: str) -> bool:
        """Return ``True`` if *doc_id* is present in the collection."""
        if not self._ready:
            return False
        result = self._collection.get(ids=[doc_id], include=[])
        return bool(result["ids"])
