"""WeaviateVectorStore — Weaviate-backed implementation of the VectorStore Protocol.

Uses the Weaviate v4 Python client (``weaviate-client>=4.6``) to store and query
dense vectors in a Weaviate collection.

Similarity metric: cosine distance via Weaviate's built-in HNSW index with
``vector_cosine_ops``.  Returned score = ``1.0 − distance`` so that 1.0 means
identical direction and 0.0 means orthogonal vectors.

The caller is responsible for providing an open Weaviate client; the store does
**not** manage the client lifecycle (connect / close).  Collection creation
happens lazily on the first :meth:`upsert` call (or on an explicit call to
:meth:`ensure_collection`).

``import weaviate.classes.config`` and ``import weaviate.classes.query`` are
**deferred** to the first ``_ensure_collection`` / ``search`` call so that
importing this module without the ``weaviate`` extra installed does not raise an
``ImportError``.

Internal document identity uses a deterministic UUID-5 derived from ``doc_id``
(namespace: a fixed project UUID), so no internal ID mapping dict is needed.
"""

from __future__ import annotations

import json
import re
import uuid as _uuid_module
from typing import Any

from llm_agents.rag.vector_store._store import SearchResult

# ---------------------------------------------------------------------------
# Collection name validation
# ---------------------------------------------------------------------------

# Weaviate collection names must start with an uppercase letter.
_SAFE_COLLECTION = re.compile(r"^[A-Z][A-Za-z0-9_]{0,62}$")


def _check_collection_name(name: str) -> str:
    """Validate a Weaviate collection name; raise :class:`ValueError` on unsafe values.

    Weaviate requires collection names to start with an uppercase letter.

    Args:
        name: Candidate collection name.

    Returns:
        The name unchanged when it passes validation.

    Raises:
        ValueError: If ``name`` is not a valid Weaviate collection name.
    """
    if not _SAFE_COLLECTION.match(name):
        raise ValueError(
            f"Invalid Weaviate collection name {name!r}. "
            "Must start with an uppercase letter and contain only "
            "ASCII letters, digits, and underscores (max 63 chars)."
        )
    return name


# ---------------------------------------------------------------------------
# Deterministic UUID helper
# ---------------------------------------------------------------------------

# Fixed namespace UUID for this project.  Changing it invalidates all stored UUIDs.
_WEAVIATE_NS = _uuid_module.UUID("d6f0a2b4-1e3c-5a7f-9b2d-4e6c8a0f2b1e")


def _doc_uuid(doc_id: str) -> str:
    """Return a deterministic UUID-5 for *doc_id* within the project namespace.

    The same *doc_id* always maps to the same UUID, enabling upsert without an
    internal ID dict.
    """
    return str(_uuid_module.uuid5(_WEAVIATE_NS, doc_id))


# ---------------------------------------------------------------------------
# WeaviateVectorStore
# ---------------------------------------------------------------------------


class WeaviateVectorStore:
    """Weaviate-backed vector store using cosine similarity.

    Vectors are stored in a Weaviate collection with an HNSW index configured
    for cosine distance.  Score returned = ``1.0 − cosine_distance`` (1.0 =
    identical, 0.0 = orthogonal, −1.0 = opposite).

    Each document is stored as a Weaviate object with two text properties:

    - ``doc_id`` — the caller-supplied identifier.
    - ``metadata_json`` — metadata serialised as a JSON string.

    Document identity in Weaviate uses a deterministic UUID-5 derived from
    ``doc_id`` via :func:`_doc_uuid`; no internal ID mapping is maintained.

    Args:
        client:          An open Weaviate v4 client (``weaviate.WeaviateClient``
                         or any object with a compatible
                         ``.collections.exists/get/create`` interface).  The
                         store does not manage the client lifecycle.
        collection_name: Name of the Weaviate collection to use.  Must start
                         with an uppercase letter and contain only ASCII
                         letters, digits, and underscores (max 63 chars).
        dimensions:      Embedding dimensionality.  If *None* (default), the
                         value is inferred from the first :meth:`upsert` call.
                         All subsequent upserts must supply the same length.

    Raises:
        ValueError: At construction time if *collection_name* is invalid.

    Example::

        import weaviate
        client = weaviate.connect_to_local()
        store = WeaviateVectorStore(client, collection_name="RagDocs")
        store.upsert("doc1", embedding, {"source": "wiki"})
        results = store.search(query_vec, top_k=5)
        client.close()
    """

    def __init__(
        self,
        client: Any,
        collection_name: str = "LlmVectors",
        dimensions: int | None = None,
    ) -> None:
        self._client = client
        self._collection_name = _check_collection_name(collection_name)
        self._dimensions: int | None = dimensions
        self._collection: Any = None
        self._ready: bool = False

    # ------------------------------------------------------------------
    # Collection setup (deferred)
    # ------------------------------------------------------------------

    def _ensure_collection(self) -> None:
        """Get or create the Weaviate collection.

        If the collection already exists it is fetched; otherwise it is created
        with an HNSW index using cosine distance.  Defers
        ``import weaviate.classes.config`` to this call.
        """
        import weaviate.classes.config as wvc  # noqa: PLC0415

        if self._client.collections.exists(self._collection_name):
            self._collection = self._client.collections.get(self._collection_name)
        else:
            self._collection = self._client.collections.create(
                name=self._collection_name,
                vectorizer_config=wvc.Configure.Vectorizer.none(),
                vector_index_config=wvc.Configure.VectorIndex.hnsw(
                    distance_metric=wvc.VectorDistances.COSINE,
                ),
                properties=[
                    wvc.Property(name="doc_id", data_type=wvc.DataType.TEXT),
                    wvc.Property(name="metadata_json", data_type=wvc.DataType.TEXT),
                ],
            )
        self._ready = True

    def ensure_collection(self) -> None:
        """Explicitly get or create the Weaviate collection.

        Called automatically on the first :meth:`upsert`.  Call this method
        directly to initialise the store before querying a pre-existing
        collection without needing to upsert first.
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

        On the first call, the collection is created if it does not yet exist
        (see :meth:`_ensure_collection`).  Uses a deterministic UUID-5 derived
        from *doc_id* to identify objects in Weaviate.

        Args:
            doc_id:   Unique document identifier.
            vector:   Embedding vector.  Length must match established
                      dimensionality.
            metadata: Optional key-value metadata serialised as a JSON string
                      inside the Weaviate object.  The dict is copied; caller
                      mutations after this call do not affect stored state.

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
        if not self._ready:
            self._ensure_collection()

        uid = _doc_uuid(doc_id)
        props = {
            "doc_id": doc_id,
            "metadata_json": json.dumps(dict(metadata) if metadata else {}),
        }
        existing = self._collection.query.fetch_object_by_id(uid)
        if existing is None:
            self._collection.data.insert(properties=props, vector=vector, uuid=uid)
        else:
            self._collection.data.replace(uuid=uid, properties=props, vector=vector)

    def delete(self, doc_id: str) -> bool:
        """Remove the entry for *doc_id*.

        Returns:
            ``True`` if the entry existed and was removed; ``False`` otherwise.
            Always returns ``False`` before the first :meth:`upsert` call or
            :meth:`ensure_collection` call.
        """
        if not self._ready:
            return False
        uid = _doc_uuid(doc_id)
        existing = self._collection.query.fetch_object_by_id(uid)
        if existing is None:
            return False
        self._collection.data.delete_by_id(uid)
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

        Score is computed as ``1.0 − cosine_distance`` so that 1.0 means
        identical and 0.0 means orthogonal vectors.

        Returns an empty list before the first :meth:`upsert` (or
        :meth:`ensure_collection`) call.

        Args:
            query_vector: Query embedding vector.
            top_k:        Maximum number of results to return.

        Returns:
            List of :class:`SearchResult` sorted by descending score (Weaviate
            returns results in ascending distance order, so the list is already
            in descending similarity order).
        """
        if not self._ready:
            return []
        from weaviate.classes.query import MetadataQuery  # noqa: PLC0415

        result = self._collection.query.near_vector(
            near_vector=query_vector,
            limit=top_k,
            return_metadata=MetadataQuery(distance=True),
        )
        return [
            SearchResult(
                doc_id=obj.properties["doc_id"],
                score=1.0 - float(obj.metadata.distance),
                metadata=json.loads(obj.properties["metadata_json"]),
            )
            for obj in result.objects
        ]

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the total number of objects in the collection.

        Issues an aggregate ``over_all(total_count=True)`` query.  Returns 0
        before :meth:`upsert` or :meth:`ensure_collection` is called.
        """
        if not self._ready:
            return 0
        result = self._collection.aggregate.over_all(total_count=True)
        return int(result.total_count) if result.total_count is not None else 0

    def __contains__(self, doc_id: str) -> bool:
        """Return ``True`` if *doc_id* is present in the collection."""
        if not self._ready:
            return False
        uid = _doc_uuid(doc_id)
        return self._collection.query.fetch_object_by_id(uid) is not None
