"""ElasticsearchVectorStore — Elasticsearch-backed implementation of the VectorStore Protocol.

Uses the Elasticsearch vector database (``elasticsearch>=8.0``) with a ``dense_vector``
field and HNSW approximate nearest-neighbour search configured with
``similarity: cosine``.

Score conversion: Elasticsearch knn returns ``(1 + cosine_similarity) / 2`` to keep
scores non-negative (Lucene requirement).  This adapter converts back to cosine
similarity: ``score = hit["_score"] * 2 − 1``, giving 1.0 = identical,
0.0 = orthogonal, −1.0 = opposite directions.

The caller is responsible for providing an open Elasticsearch client; the store does
**not** manage the client lifecycle.  Index creation happens lazily on the first
:meth:`upsert` call (or an explicit call to :meth:`ensure_index`).

Unlike the FAISS and pgvector adapters, **no deferred import of** ``elasticsearch``
**is needed** — all operations go through the injected client object, so this module
imports cleanly without the ``elasticsearch`` extra installed.

The Elasticsearch ``dense_vector`` mapping requires ``dims`` to be declared at index
creation time.  The adapter infers ``dims`` from the first :meth:`upsert` call.
Calling :meth:`ensure_index` explicitly on a non-existent index requires that
``dimensions`` be passed to the constructor.
"""

from __future__ import annotations

import json
import re
from typing import Any

from llm_agents.rag.vector_store._store import SearchResult

# ---------------------------------------------------------------------------
# Index name validation
# ---------------------------------------------------------------------------

# Safe subset of Elasticsearch index name rules:
#   - lowercase letters, digits, underscores, and hyphens only
#   - must start with a lowercase letter or digit (not '-', '_', '+')
#   - max 255 bytes
_SAFE_ES_INDEX = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _check_index_name(name: str) -> str:
    """Validate an Elasticsearch index name; raise :class:`ValueError` on invalid values.

    Checks a safe subset of Elasticsearch naming rules, giving an early and descriptive
    error before the Elasticsearch client is involved.

    Args:
        name: Candidate index name.

    Returns:
        The name unchanged when it passes validation.

    Raises:
        ValueError: If ``name`` violates any naming rule.
    """
    if not name:
        raise ValueError("Elasticsearch index name must not be empty.")
    if len(name) > 255:
        raise ValueError(
            f"Elasticsearch index name {name!r} must be at most 255 characters."
        )
    if not _SAFE_ES_INDEX.match(name):
        raise ValueError(
            f"Invalid Elasticsearch index name {name!r}. "
            "Must start with a lowercase letter or digit and contain only "
            "lowercase letters, digits, underscores, and hyphens."
        )
    return name


# ---------------------------------------------------------------------------
# ElasticsearchVectorStore
# ---------------------------------------------------------------------------


class ElasticsearchVectorStore:
    """Elasticsearch-backed vector store using cosine similarity.

    Vectors are stored in an Elasticsearch index with a ``dense_vector`` field
    configured for HNSW approximate nearest-neighbour search and cosine similarity.
    Score returned = ``hit._score * 2 − 1`` (1.0 = identical, 0.0 = orthogonal,
    −1.0 = opposite directions).

    Elasticsearch returns knn ``_score`` as ``(1 + cosine_similarity) / 2`` to satisfy
    Lucene's requirement that scores be non-negative.  This adapter reverses that
    transformation so returned scores are consistent with other ``VectorStore``
    implementations.

    The ``dense_vector`` mapping requires ``dims`` to be declared at index creation
    time.  Dimensions are inferred from the first :meth:`upsert` call.  If
    :meth:`ensure_index` is called explicitly on a non-existent index, ``dimensions``
    must be passed to the constructor.

    Args:
        client:     An open Elasticsearch client (``elasticsearch.Elasticsearch`` or
                    any object with compatible ``indices`` and document API methods).
                    The store does not manage the client lifecycle.
        index_name: Name of the Elasticsearch index.  Must start with a lowercase
                    letter or digit and contain only lowercase letters, digits,
                    underscores, and hyphens.  Max 255 characters.
        dimensions: Embedding dimensionality.  If *None* (default), the value is
                    inferred from the first :meth:`upsert` call.  Required when
                    calling :meth:`ensure_index` on a non-existent index.

    Raises:
        ValueError: At construction time if *index_name* is invalid.

    Example::

        from elasticsearch import Elasticsearch
        client = Elasticsearch("http://localhost:9200")
        store = ElasticsearchVectorStore(client, index_name="rag_docs", dimensions=1536)
        store.upsert("doc1", embedding, {"source": "wiki"})
        results = store.search(query_vec, top_k=5)
    """

    def __init__(
        self,
        client: Any,
        index_name: str = "llm_vectors",
        dimensions: int | None = None,
    ) -> None:
        self._client = client
        self._index_name = _check_index_name(index_name)
        self._dimensions: int | None = dimensions
        self._ready: bool = False

    # ------------------------------------------------------------------
    # Index setup
    # ------------------------------------------------------------------

    def _ensure_index(self) -> None:
        """Get or create the Elasticsearch index with a cosine dense_vector mapping.

        If the index already exists, this sets ``_ready = True`` without re-creating.
        If the index does not exist and ``_dimensions`` is known, the index is created
        with ``dense_vector`` (HNSW, cosine similarity).  Raises :class:`ValueError` if
        ``_dimensions`` is not yet set and the index does not exist.
        """
        if self._client.indices.exists(index=self._index_name):
            self._ready = True
            return
        if self._dimensions is None:
            raise ValueError(
                f"Cannot create Elasticsearch index {self._index_name!r}: "
                "dimensions are not known. "
                "Pass dimensions= to the constructor or call upsert first "
                "(dimensions are inferred from the first vector)."
            )
        self._client.indices.create(
            index=self._index_name,
            mappings={
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": self._dimensions,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "metadata_json": {"type": "keyword"},
                }
            },
        )
        self._ready = True

    def ensure_index(self) -> None:
        """Explicitly get or create the Elasticsearch index.

        Called automatically on the first :meth:`upsert`.  Call this method directly
        to initialise the store before querying a pre-existing index without needing
        to upsert first.

        Raises:
            ValueError: If the index does not exist and ``dimensions`` was not passed
                        to the constructor.
        """
        self._ensure_index()

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

        Uses ``client.index()`` with ``id=doc_id`` for native insert-or-replace
        semantics (Elasticsearch replaces the document if the ID already exists).
        On the first call, the index is created if it does not yet exist (see
        :meth:`_ensure_index`).

        Metadata is serialised as a JSON string in a ``metadata_json`` keyword field,
        keeping the index schema fixed regardless of metadata shape.

        Args:
            doc_id:   Unique document identifier (used directly as the Elasticsearch
                      ``_id``).
            vector:   Embedding vector.  Length must match established dimensionality.
            metadata: Optional key-value metadata.  The dict is copied; caller
                      mutations after this call do not affect stored state.

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
            self._ensure_index()
        self._client.index(
            index=self._index_name,
            id=doc_id,
            document={
                "doc_id": doc_id,
                "embedding": vector,
                "metadata_json": json.dumps(dict(metadata) if metadata else {}),
            },
        )

    def delete(self, doc_id: str) -> bool:
        """Remove the entry for *doc_id*.

        Returns:
            ``True`` if the entry existed and was removed; ``False`` otherwise.
            Always returns ``False`` before the first :meth:`upsert` call or
            :meth:`ensure_index` call.
        """
        if not self._ready:
            return False
        if not self._client.exists(index=self._index_name, id=doc_id):
            return False
        self._client.delete(index=self._index_name, id=doc_id)
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

        Uses the Elasticsearch ``knn`` query parameter with the ``dense_vector`` field.
        Elasticsearch knn returns scores as ``(1 + cosine_similarity) / 2``.  This
        method converts them back to cosine similarity: ``score = _score * 2 − 1``.

        Args:
            query_vector: Query embedding vector.
            top_k:        Maximum number of results to return.

        Returns:
            List of :class:`SearchResult` sorted by descending score (Elasticsearch
            returns knn results in descending ``_score`` order).
        """
        if not self._ready:
            return []
        response = self._client.search(
            index=self._index_name,
            knn={
                "field": "embedding",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": max(top_k * 10, top_k + 1),
            },
            size=top_k,
        )
        return [
            SearchResult(
                doc_id=hit["_source"]["doc_id"],
                score=float(hit["_score"]) * 2.0 - 1.0,
                metadata=json.loads(hit["_source"]["metadata_json"]),
            )
            for hit in response["hits"]["hits"]
        ]

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of indexed documents via ``client.count()``.

        Returns 0 before :meth:`upsert` or :meth:`ensure_index` is called.
        """
        if not self._ready:
            return 0
        return int(self._client.count(index=self._index_name)["count"])

    def __contains__(self, doc_id: str) -> bool:
        """Return ``True`` if *doc_id* is present in the index."""
        if not self._ready:
            return False
        return bool(self._client.exists(index=self._index_name, id=doc_id))
