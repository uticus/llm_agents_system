# rag/vector_store

## Overview

The vector store module provides persistent (or in-process) storage for embedding vectors and associated metadata, along with similarity search over those vectors. It is the core index that makes retrieval-augmented generation possible: at indexing time, chunk embeddings are written into the store; at retrieval time, a query embedding is used to find the nearest stored vectors. The module defines the `VectorStore` structural protocol, a `SearchResult` dataclass for query results, and five implementations: `InMemoryVectorStore` (brute-force in-memory, for tests and prototyping), `FAISSVectorStore` (FAISS flat inner-product index with lazy index rebuild, requires the `rag` extra), `PgVectorStore` (PostgreSQL pgvector extension, persistent and durable, requires the `pgvector` extra), `WeaviateVectorStore` (Weaviate HNSW, requires the `weaviate` extra), and `ChromaVectorStore` (Chroma HNSW with cosine similarity, requires the `chroma` extra). Production deployments swap in any backend behind the same protocol.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `SearchResult` | dataclass | Single result from a vector search: doc_id, score, metadata. |
| `VectorStore` | Protocol | Structural interface for vector stores: upsert, search, delete. |
| `InMemoryVectorStore` | class | Brute-force in-memory store with cosine similarity; for tests and prototyping. |
| `FAISSVectorStore` | class | FAISS flat inner-product index with L2-normalised cosine search; requires `rag` extra. |
| `PgVectorStore` | class | PostgreSQL pgvector-backed store with IVFFlat approximate search; requires `pgvector` extra. |
| `WeaviateVectorStore` | class | Weaviate HNSW-backed store with cosine similarity; requires `weaviate` extra. |
| `ChromaVectorStore` | class | Chroma HNSW-backed store with cosine similarity; requires `chroma` extra. |

### `SearchResult`

```python
@dataclass
class SearchResult:
    doc_id:   str
    score:    float                   # cosine similarity in [-1.0, 1.0]
    metadata: dict[str, Any] = field(default_factory=dict)
```

Results are always returned sorted by descending `score`. The `metadata` dict is a copy of what was stored at upsert time.

### `VectorStore` Protocol

```python
@runtime_checkable
class VectorStore(Protocol):
    def upsert(
        self,
        doc_id:   str,
        vector:   list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    def search(
        self,
        query_vector: list[float],
        top_k:        int = 5,
    ) -> list[SearchResult]: ...

    def delete(self, doc_id: str) -> bool: ...
```

The protocol is `@runtime_checkable`. All three methods are required for a conforming implementation.

### `InMemoryVectorStore`

```python
class InMemoryVectorStore:
    def __init__(self) -> None: ...
    def upsert(self, doc_id: str, vector: list[float], metadata: dict[str, Any] | None = None) -> None: ...
    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]: ...
    def delete(self, doc_id: str) -> bool: ...

    def __len__(self) -> int: ...        # number of stored vectors
    def __contains__(self, doc_id: str) -> bool: ...
```

Internally stores `_Entry(vector, metadata)` objects in a dict keyed by `doc_id`. Vectors and metadata are shallow-copied on write to isolate stored state from caller mutations.

### `FAISSVectorStore`

Requires: `pip install llm-agents-system[rag]` (`faiss-cpu>=1.8`).

```python
class FAISSVectorStore:
    def __init__(self, dimensions: int | None = None) -> None: ...
    def upsert(self, doc_id: str, vector: list[float], metadata: dict[str, Any] | None = None) -> None: ...
    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]: ...
    def delete(self, doc_id: str) -> bool: ...

    def __len__(self) -> int: ...
    def __contains__(self, doc_id: str) -> bool: ...
```

Backed by `faiss.IndexFlatIP` (exact inner-product search on L2-normalised vectors, equivalent to cosine similarity). The index is rebuilt lazily from the source-of-truth `_data` dict whenever a mutation has occurred since the last search. `import faiss` and `import numpy` are deferred to the first `_build_index` call so the module imports cleanly without the `rag` extra.

### `PgVectorStore`

Requires: `pip install llm-agents-system[pgvector]` (`psycopg[binary]>=3.2`, `pgvector>=0.3`) and a running PostgreSQL server with the `pgvector` extension installed.

```python
class PgVectorStore:
    def __init__(
        self,
        connection: Any,           # open psycopg.Connection
        table: str = "llm_vectors",
        dimensions: int | None = None,
    ) -> None: ...
    def upsert(self, doc_id: str, vector: list[float], metadata: dict[str, Any] | None = None) -> None: ...
    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]: ...
    def delete(self, doc_id: str) -> bool: ...

    def __len__(self) -> int: ...
    def __contains__(self, doc_id: str) -> bool: ...
```

The caller provides an open `psycopg.Connection`; the store does not manage connection lifecycle. Table, extension, and index creation happen lazily on the first `upsert`. `import pgvector.psycopg` is deferred to the first `_ensure_table` call. Table identifier is validated against a safe-identifier regex to prevent SQL injection.

### `WeaviateVectorStore`

Requires: `pip install llm-agents-system[weaviate]` (`weaviate-client>=4.6`) and a running Weaviate instance.

```python
class WeaviateVectorStore:
    def __init__(
        self,
        client: Any,               # open weaviate.WeaviateClient
        collection_name: str = "LlmVectors",
        dimensions: int | None = None,
    ) -> None: ...
    def upsert(self, doc_id: str, vector: list[float], metadata: dict[str, Any] | None = None) -> None: ...
    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]: ...
    def delete(self, doc_id: str) -> bool: ...
    def ensure_collection(self) -> None: ...  # explicit init for pre-existing collections

    def __len__(self) -> int: ...
    def __contains__(self, doc_id: str) -> bool: ...
```

The caller provides an open `weaviate.WeaviateClient`; the store does not manage the client lifecycle. Collection, HNSW index (cosine distance), and property schema creation happen lazily on the first `upsert` (or an explicit `ensure_collection()` call). Each document is stored as a Weaviate object with a deterministic UUID-5 derived from `doc_id` (no internal ID mapping dict needed). Metadata is stored as a JSON string in a `metadata_json` text property. `import weaviate.classes.config` and `import weaviate.classes.query` are deferred to their first call site. Collection names must start with an uppercase letter (Weaviate convention) and are validated at construction time.

### `ChromaVectorStore`

Requires: `pip install llm-agents-system[chroma]` (`chromadb>=0.5`).

```python
class ChromaVectorStore:
    def __init__(
        self,
        client: Any,               # open Chroma client (chromadb.Client or PersistentClient)
        collection_name: str = "llm_vectors",
        dimensions: int | None = None,
    ) -> None: ...
    def upsert(self, doc_id: str, vector: list[float], metadata: dict[str, Any] | None = None) -> None: ...
    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]: ...
    def delete(self, doc_id: str) -> bool: ...
    def ensure_collection(self) -> None: ...  # explicit init for pre-existing collections

    def __len__(self) -> int: ...
    def __contains__(self, doc_id: str) -> bool: ...
```

The caller provides an open Chroma client; the store does not manage the client lifecycle. Collection creation with `hnsw:space=cosine` happens lazily on the first `upsert` (or an explicit `ensure_collection()` call). Chroma's native `collection.upsert()` provides atomic insert-or-replace semantics — no check-then-branch is needed. Score is returned as `1.0 - cosine_distance`. Unlike other adapters, `chromadb` is never imported inside `_chroma_store.py` — all operations go through the injected client object, so the module imports cleanly without the `chroma` extra installed. Collection names are validated at construction time (3–63 chars, alphanumeric start/end, letters/digits/underscores/dots/hyphens, no consecutive dots).

---

## Architecture

### Conceptual view

```
   [ Indexer ]
        |
        | upsert(chunk_id, vector, metadata)
        v
  +-----------------+         +-----------------------+
  | VectorStore     |  <---   | InMemoryVectorStore   |  (test / prototype)
  |  Protocol       |         +-----------------------+
  |  upsert         |  <---   | FAISSVectorStore      |  (local ANN, rag extra)
  |  search         |         +-----------------------+
  |  delete         |  <---   | PgVectorStore         |  (persistent SQL, pgvector extra)
  +-----------------+         +-----------------------+
                       <---   | WeaviateVectorStore   |  (managed HNSW, weaviate extra)
                              +-----------------------+
                       <---   | ChromaVectorStore     |  (embedded/server HNSW, chroma extra)
                              +-----------------------+
        ^
        | search(query_vector, top_k)
        |
   [ DenseRetriever ]
```

The vector store sits at the centre of the RAG data plane. Writes come from the `Indexer`; reads come from the `DenseRetriever`. Neither component depends on the concrete implementation — any object satisfying the `VectorStore` protocol is interchangeable.

### Data flow

**Write path (indexing):**
1. `Indexer` calls `store.upsert(chunk_id, vector, metadata)`.
2. `InMemoryVectorStore` copies the vector and metadata into `_Entry` and stores it keyed by `chunk_id`.
3. `FAISSVectorStore` stores vector and metadata in `_data` dict and marks `_dirty = True`.
4. `PgVectorStore` issues `INSERT ... ON CONFLICT DO UPDATE` to PostgreSQL.
5. `WeaviateVectorStore` calls `fetch_object_by_id` to check existence, then `data.insert` (new) or `data.replace` (update existing).
6. `ChromaVectorStore` calls `collection.upsert(ids=[...], embeddings=[...], metadatas=[...])` — native atomic insert-or-replace, no check-then-branch needed.
7. If the key already exists, the old entry is replaced (idempotent upsert) in all implementations.

**Read path (retrieval):**
1. `DenseRetriever` calls `store.search(query_vector, top_k=k)`.
2. `InMemoryVectorStore`: computes cosine similarity against every stored vector (O(n) brute force).
3. `FAISSVectorStore`: if `_dirty`, rebuilds `IndexFlatIP` from `_data`; L2-normalises query; calls `index.search`.
4. `PgVectorStore`: executes `SELECT doc_id, 1.0 - (embedding <=> %s::vector) AS score FROM <table> ORDER BY dist LIMIT k` via the pgvector `<=>` cosine-distance operator.
5. `WeaviateVectorStore`: calls `collection.query.near_vector(near_vector=..., limit=k, return_metadata=MetadataQuery(distance=True))`; score = `1.0 - obj.metadata.distance`.
6. `ChromaVectorStore`: clamps `n_results = min(top_k, collection.count())`; calls `collection.query(query_embeddings=[...], n_results=n, include=["distances", "metadatas"])`; score = `1.0 - distance`.
7. Results are returned as `list[SearchResult]` sorted by descending score.

**Delete path:**
1. Caller calls `store.delete(doc_id)`.
2. `InMemoryVectorStore` / `FAISSVectorStore`: removes from internal dict; FAISS marks `_dirty = True` (index rebuilt on next search).
3. `PgVectorStore`: issues `DELETE FROM <table> WHERE doc_id = %s`; reads `rowcount` to determine whether a row existed.
4. `WeaviateVectorStore`: calls `fetch_object_by_id(uuid5(doc_id))`; if not None, calls `data.delete_by_id(uuid)`.
5. `ChromaVectorStore`: calls `collection.get(ids=[doc_id], include=[])` to check existence; if found, calls `collection.delete(ids=[doc_id])`.
6. Returns `True` if the entry existed and was removed, `False` otherwise.

### Key abstractions

**`SearchResult`** separates the vector store's view of a result (doc_id + score + metadata) from the retrieval layer's view (`RetrievedPassage` with text). The vector store does not know what text a chunk contains; it only knows vectors and metadata. The mapping from chunk_id back to text is done by the retriever, which looks for a `"text"` key in `metadata`.

**`VectorStore` Protocol** enforces three operations: write (upsert), read (search), and delete. Delete is included because production RAG systems must be able to remove stale or retracted documents. The protocol deliberately excludes bulk operations and persistence management to keep it minimal.

**`InMemoryVectorStore`** internal `_cosine` function handles the zero-norm edge case (returns 0.0 for zero vectors) and uses `zip(a, b, strict=False)` so mismatched-length vectors do not raise but silently compute a partial dot product — callers are responsible for dimension consistency.

**`FAISSVectorStore`** maintains a source-of-truth Python dict (`_data`) separate from the FAISS index. The FAISS flat index does not support native deletion, so deletion removes from `_data` and marks `_dirty = True`. The index is fully rebuilt from `_data` on the next `search` call. This keeps correctness trivial at the cost of O(n) rebuild time.

**`PgVectorStore`** uses the injection pattern: the caller passes an open `psycopg.Connection`. This makes the store testable without a running server (mock the connection). The `_ensure_table` method is called lazily on the first `upsert`, which creates the `vector` extension, the table, and an IVFFlat index in a single transaction. Table names are validated with a strict regex to prevent SQL injection — only parameterised queries are used for data values.

**`WeaviateVectorStore`** uses the same injection pattern: the caller passes an open `weaviate.WeaviateClient`. Collection creation is lazy (first `upsert` or explicit `ensure_collection()`). Document identity in Weaviate requires a UUID; a deterministic UUID-5 is derived from `doc_id` using a fixed project namespace, eliminating the need for an internal ID-mapping dict. Metadata is stored as a JSON string in a `metadata_json` text property rather than as individual Weaviate properties, keeping the schema fixed and independent of metadata shape. Upsert is a check-then-branch: `fetch_object_by_id` determines whether to call `data.insert` or `data.replace`.

**`ChromaVectorStore`** uses the same injection pattern: the caller passes an open Chroma client (`chromadb.Client` or `PersistentClient`). Collection creation with `hnsw:space=cosine` is lazy (first `upsert` or explicit `ensure_collection()`). Chroma's native `collection.upsert()` provides atomic insert-or-replace — no check-then-branch is required, unlike Weaviate. `chromadb` is never imported inside the adapter module; all calls go through the injected client, so the module loads cleanly without the `chroma` extra. Metadata is stored as a Chroma metadata dict (shallow-copied on write). Search clamps `n_results = min(top_k, collection.count())` to avoid Chroma raising when `n_results` exceeds stored items.

---

## Design decisions and tradeoffs

- **Decision**: Cosine similarity rather than L2 (Euclidean) distance as the search metric.
  **Why**: Cosine similarity is the standard metric for semantic text embeddings and is direction-invariant (invariant to vector magnitude), which makes it robust when embedders produce un-normalised outputs.
  **Tradeoff**: L2 is computationally cheaper and is required by some approximate nearest-neighbour libraries (FAISS IVF). When integrating FAISS, callers must either normalise vectors or choose the L2 index type.

- **Decision**: Upsert semantics (insert-or-replace) rather than insert-or-fail.
  **Why**: Re-indexing the same document repeatedly is a common operation (content update, configuration change). Upsert makes re-indexing idempotent without requiring a separate check-then-insert.
  **Tradeoff**: Upsert silently overwrites a vector with a different embedding from a previous indexing run, which can cause subtle ranking changes that are hard to debug.

- **Decision**: `delete` returns `bool` rather than raising on missing key.
  **Why**: The caller often does not know whether a chunk ID is currently indexed; a boolean return avoids a try/except and makes conditional logic cleaner.
  **Tradeoff**: A missing key is silently swallowed; callers expecting strict existence guarantees must check the return value explicitly.

- **Decision**: `InMemoryVectorStore` performs O(n) brute-force search.
  **Why**: No external dependencies, always correct, and adequate for test corpora of up to a few thousand vectors.
  **Tradeoff**: Search time scales linearly with store size. At 100 000+ vectors, query latency becomes unacceptable; a production backend (FAISS, pgvector with HNSW, Weaviate) is required.

- **Decision**: Metadata is shallow-copied on both write and read.
  **Why**: Prevents callers from mutating stored metadata after upsert, and prevents the store's internal state from being exposed through search results.
  **Tradeoff**: Deep-nested objects within metadata (nested dicts, lists) are shared by reference. Mutations to deeply nested values will corrupt stored state.

- **Decision**: `FAISSVectorStore` uses full index rebuild on every dirty search rather than incremental insertion-only.
  **Why**: FAISS flat indices do not support efficient deletion. Full rebuild from the authoritative `_data` dict is simple, correct, and avoids index/dict state divergence.
  **Tradeoff**: O(n) rebuild cost on every search after any mutation. For n > ~100 000 vectors, rebuild time exceeds acceptable latency; a FAISS HNSW index with soft-delete filtering or a dedicated vector database should be used instead.

- **Decision**: `PgVectorStore` uses IVFFlat index (`vector_cosine_ops`) created at table-init time.
  **Why**: IVFFlat is supported by all pgvector versions ≥ 0.2 and provides sub-linear approximate search with predictable recall. HNSW (faster but higher memory) is an alternative for pgvector ≥ 0.5.
  **Tradeoff**: IVFFlat requires at least `lists × 39` rows for good recall. On small tables (< a few hundred rows), the index is slower than a sequential scan and pgvector may ignore it. For large tables the index should be rebuilt with `VACUUM ANALYZE` after bulk inserts.

- **Decision**: `PgVectorStore` receives an injected connection rather than a connection string.
  **Why**: Connection management (pooling, SSL, reconnect logic) belongs to the caller. Injection makes the store testable with a mock — no live server needed for unit tests.
  **Tradeoff**: The caller is responsible for keeping the connection open and handling reconnects. A dropped connection raises a `psycopg` error inside the store rather than being handled transparently.

- **Decision**: `PgVectorStore` stores metadata as JSONB rather than separate columns.
  **Why**: Metadata schema is not known at class-definition time (it varies by corpus). JSONB allows arbitrary key-value pairs and supports GIN indexing for metadata filtering if needed in the future.
  **Tradeoff**: Filtering on metadata requires `metadata->>'key' = 'value'` JSON path queries rather than indexed column lookups. For high-cardinality filters a separate column or GIN index on metadata is required.

- **Decision**: `WeaviateVectorStore` uses a deterministic UUID-5 derived from `doc_id` rather than maintaining an internal `doc_id → uuid` dict.
  **Why**: Weaviate objects require UUIDs. Generating a UUID-5 from a fixed namespace + `doc_id` makes the UUID predictable without any state, and the same UUID is produced on every process restart — enabling idempotent upsert and delete across restarts.
  **Tradeoff**: UUID-5 has a theoretical collision probability (negligible in practice). The fixed namespace is baked into the code; changing it would invalidate all stored object IDs.

- **Decision**: `WeaviateVectorStore` stores metadata as a JSON-serialised string in a single `metadata_json` text property rather than as individual Weaviate object properties.
  **Why**: Weaviate's schema requires all property names and types to be declared at collection-creation time. Dynamic metadata shapes (different keys per document) cannot be accommodated in a static schema without using a blob field.
  **Tradeoff**: Metadata fields cannot be filtered at the Weaviate layer (no `where: {path: ["metadata_json"], valueString: ...}` on arbitrary keys). If pre-search metadata filtering is required, use individual Weaviate properties or a separate filter step.

- **Decision**: `WeaviateVectorStore` upsert checks existence via `fetch_object_by_id` before deciding to `insert` or `replace`.
  **Why**: Weaviate v4 has no single atomic upsert API. The check-then-branch is explicit and testable; try/except on insert would catch legitimate errors (network failure, schema mismatch) along with duplicate-UUID errors.
  **Tradeoff**: Two API calls per upsert instead of one. In high-throughput scenarios, a batch upsert API or a try/except approach on a narrowly typed exception may be preferred.

- **Decision**: `ChromaVectorStore` uses Chroma's native `collection.upsert()` for atomic insert-or-replace.
  **Why**: Unlike Weaviate, Chroma provides a single `upsert` call with insert-or-replace semantics. No check-then-branch is needed, reducing round-trips and eliminating the race condition inherent in check-then-write.
  **Tradeoff**: No change — Chroma's upsert is both simpler and more correct than the alternatives.

- **Decision**: `ChromaVectorStore` never imports `chromadb` inside the module — all operations go through the injected client.
  **Why**: Unlike FAISS (deferred `import faiss`) and pgvector (deferred `import pgvector`), Chroma has no module-level constants or types that must be resolved at definition time. Injecting the client is sufficient. This means the module imports with zero overhead even without the `chroma` extra installed.
  **Tradeoff**: The caller must construct the client externally, which is already required by the injection pattern. No additional burden compared to other adapters.

- **Decision**: `ChromaVectorStore` clamps `n_results = min(top_k, collection.count())` on every search.
  **Why**: Chroma raises `chromadb.errors.InvalidCollectionException` (or similar) if `n_results` exceeds the number of stored items. The clamp avoids this edge case and makes search idempotent on sparse collections.
  **Tradeoff**: An extra `collection.count()` call per search adds one round-trip. This is acceptable; alternatives (catch-and-return-empty) would obscure the failure mode.

---

## Scaling concerns

- **InMemoryVectorStore — O(n) search**: Search computes cosine similarity against every stored vector. At 10 000 vectors this is fast; at 1 000 000 vectors it is completely impractical. Threshold for switching to an ANN backend is roughly 10 000–50 000 vectors depending on latency requirements.
- **InMemoryVectorStore — memory**: Each stored vector of dimension `d` costs ~`8d` bytes (Python float). At 1 536 dimensions (OpenAI ada-002), one million vectors cost ~12 GB in pure Python lists.
- **InMemoryVectorStore — no persistence**: All data is lost on process exit. All production use cases require a persistent backend.
- **FAISSVectorStore — O(n) rebuild**: The FAISS index is rebuilt in full from `_data` on every search after any mutation. Acceptable up to ~100 000 vectors; beyond that, rebuild time exceeds acceptable latency. Mitigation: batch writes, then query; or switch to a database-backed store.
- **FAISSVectorStore — memory**: FAISS flat index stores all vectors in RAM (32-bit floats). 1 million × 1 536 dims ≈ 6 GB. For very large corpora, IVF or PQ quantisation reduces memory but requires the `faiss-gpu` build or a dedicated vector service.
- **FAISSVectorStore — concurrency**: Not thread-safe. Concurrent mutation and search require external locking.
- **PgVectorStore — IVFFlat recall**: IVFFlat uses approximate nearest-neighbour search; recall depends on `lists` and the query-time `probes` parameter. Default `lists = 100` is appropriate for corpora of ~1 million vectors; adjust to `sqrt(n)` for best recall/speed trade-off.
- **PgVectorStore — connection management**: The store does not pool connections. For concurrent serving, use a connection pool (e.g. `psycopg_pool`) and create one `PgVectorStore` per connection, or redesign to accept a pool.
- **PgVectorStore — metadata filtering**: Metadata is stored as JSONB. Filtering on metadata (e.g. `WHERE metadata->>'source' = 'wiki'`) is not exposed through the `VectorStore` protocol. If pre-search metadata filtering is required, execute a raw SQL query before calling `search`, or extend the protocol with a `filters` parameter.
- **WeaviateVectorStore — upsert race condition**: The check-then-branch `fetch_object_by_id → insert/replace` is not atomic. Concurrent upserts for the same `doc_id` can cause a `replace` call for an object that doesn't yet exist, or an `insert` for one that already does. Weaviate raises an error in this case. Mitigation: use an external lock per `doc_id` for concurrent producers, or adopt a retry loop.
- **WeaviateVectorStore — client lifecycle**: The store does not call `client.close()`. The caller must close the client after all operations. Forgetting to close leaves an open gRPC connection to the Weaviate instance.
- **WeaviateVectorStore — metadata filtering**: Metadata is stored as a JSON string and cannot be filtered at the Weaviate query layer. Pre-search filtering requires a separate query, or redesigning the schema to use individual properties.
- **ChromaVectorStore — count() on every search**: `search` calls `collection.count()` before querying to clamp `n_results`. For very high-throughput search, this adds a round-trip per query. Mitigation: cache the count or raise the minimum at which Chroma starts refusing.
- **ChromaVectorStore — client lifecycle**: The store does not call `client.reset()` or any teardown method. The caller is responsible for managing the Chroma client lifecycle (especially with `PersistentClient` which persists to disk).
- **ChromaVectorStore — concurrency**: Chroma's embedded client is not thread-safe. For concurrent writes use Chroma server mode (`HttpClient`) and one `ChromaVectorStore` per thread, or wrap with an external lock.
- **All implementations — concurrency**: None of the implementations serialise concurrent access. Wrap in a lock or use connection pools (pgvector) for concurrent production workloads.

---

## Future improvements

- **HNSW index in PgVectorStore**: Replace IVFFlat with an HNSW index (`USING hnsw (embedding vector_cosine_ops)`) for faster approximate search with better recall at low `probes`. Requires pgvector ≥ 0.5. Make the index type configurable at construction time.
- **Async PgVectorStore**: Add `AsyncPgVectorStore` using `psycopg` async API (`await conn.execute(...)`) for use in async serving paths without blocking the event loop.
- **PgVectorStore metadata filtering**: Extend `search` with an optional `filters: dict[str, Any]` parameter that appends `WHERE metadata @> %s::jsonb` to the query for pre-search filtering. This would require a protocol extension or a subclass.
- **PgVectorStore connection pool**: Accept a `psycopg_pool.ConnectionPool` in addition to a bare connection, and acquire/release connections per operation for concurrent workloads.
- **Elasticsearch adapter**: Add an adapter for Elasticsearch with the `dense_vector` field and `script_score` or `knn` query for approximate nearest-neighbour search.
- **Bulk upsert**: Add an `upsert_batch(entries: list[tuple[str, list[float], dict]]) -> None` method to the protocol for efficient bulk loading. PostgreSQL COPY, FAISS `index.add(matrix)`, and Weaviate batch APIs all support bulk ingestion with far lower overhead than sequential upsert.
- **FAISSVectorStore HNSW mode**: Add a `metric` parameter to `FAISSVectorStore` (default `"cosine"`, option `"l2"`) and switch to `IndexHNSWFlat` for approximate search when exact search latency is unacceptable at scale.
- **WeaviateVectorStore metadata schema**: Add an optional `extra_properties` parameter to `WeaviateVectorStore` that defines additional Weaviate object properties for fields that need to be filterable at query time.
- **WeaviateVectorStore batch upsert**: Expose `upsert_batch` using `collection.data.insert_many` (Weaviate v4) for efficient bulk loading — reduces round-trips from O(n) to O(n / batch_size).
- **WeaviateVectorStore GRPC streaming search**: Use Weaviate's gRPC streaming API (`near_vector` with `return_properties` and streaming) for large result sets to reduce memory pressure on the client side.

---

## Usage examples

**Basic upsert and search:**

```python
from llm_agents.rag.vector_store import InMemoryVectorStore

store = InMemoryVectorStore()
store.upsert("doc-1", [1.0, 0.0, 0.0], metadata={"title": "First"})
store.upsert("doc-2", [0.0, 1.0, 0.0], metadata={"title": "Second"})

results = store.search([1.0, 0.0, 0.0], top_k=2)
for r in results:
    print(r.doc_id, r.score, r.metadata)
# doc-1  1.0  {"title": "First"}
# doc-2  0.0  {"title": "Second"}
```

**Idempotent re-indexing:**

```python
from llm_agents.rag.vector_store import InMemoryVectorStore

store = InMemoryVectorStore()
store.upsert("chunk-1", [1.0, 0.0])
store.upsert("chunk-1", [0.0, 1.0])  # overwrites previous entry
assert len(store) == 1
assert store.search([0.0, 1.0], top_k=1)[0].score == 1.0
```

**Delete and membership check:**

```python
from llm_agents.rag.vector_store import InMemoryVectorStore

store = InMemoryVectorStore()
store.upsert("a", [1.0, 0.0])
assert "a" in store
removed = store.delete("a")
assert removed is True
assert "a" not in store
assert store.delete("a") is False  # already gone
```

**FAISS adapter (requires `rag` extra):**

```python
from llm_agents.rag.vector_store import FAISSVectorStore

store = FAISSVectorStore()
store.upsert("doc1", [1.0, 0.0, 0.0], {"text": "first"})
store.upsert("doc2", [0.0, 1.0, 0.0], {"text": "second"})

results = store.search([1.0, 0.0, 0.0], top_k=1)
print(results[0].doc_id, results[0].score)  # doc1  1.0
```

Vectors are L2-normalised before insertion and at query time; inner-product search is equivalent to cosine similarity.

**PostgreSQL pgvector adapter (requires `pgvector` extra and a running server):**

```python
import psycopg
from llm_agents.rag.vector_store import PgVectorStore

conn = psycopg.connect("postgresql://localhost/mydb")
store = PgVectorStore(conn, table="rag_docs", dimensions=1536)

# first upsert creates the table, extension, and index
store.upsert("doc1", embedding_vector, {"source": "wiki", "page": 42})

results = store.search(query_embedding, top_k=5)
for r in results:
    print(r.doc_id, round(r.score, 3), r.metadata["source"])
```

**Weaviate adapter (requires `weaviate` extra and a running Weaviate instance):**

```python
import weaviate
from llm_agents.rag.vector_store import WeaviateVectorStore

client = weaviate.connect_to_local()  # or connect_to_weaviate_cloud(...)
store = WeaviateVectorStore(client, collection_name="RagDocs")

# first upsert creates the collection and HNSW index
store.upsert("doc1", embedding_vector, {"source": "wiki"})
store.upsert("doc1", new_embedding, {"source": "wiki_v2"})  # idempotent update

results = store.search(query_embedding, top_k=5)
for r in results:
    print(r.doc_id, round(r.score, 3), r.metadata)

client.close()
```

Query a pre-existing Weaviate collection (without upserting first):

```python
store = WeaviateVectorStore(client, collection_name="ExistingDocs")
store.ensure_collection()  # connect to existing collection; no upsert needed
results = store.search(query_embedding, top_k=10)
```

**Chroma adapter (requires `chroma` extra):**

```python
import chromadb
from llm_agents.rag.vector_store import ChromaVectorStore

# Embedded persistent client
client = chromadb.PersistentClient(path="/data/chroma")
store = ChromaVectorStore(client, collection_name="rag_docs")

# first upsert creates the collection with hnsw:space=cosine
store.upsert("doc1", embedding_vector, {"source": "wiki"})
store.upsert("doc1", new_embedding, {"source": "wiki_v2"})  # atomic replace

results = store.search(query_embedding, top_k=5)
for r in results:
    print(r.doc_id, round(r.score, 3), r.metadata)
```

Query a pre-existing Chroma collection (without upserting first):

```python
store = ChromaVectorStore(client, collection_name="existing_docs")
store.ensure_collection()  # connect to existing collection; no upsert needed
results = store.search(query_embedding, top_k=10)
```

**Swapping backends transparently (protocol-driven):**

```python
from llm_agents.rag.vector_store import VectorStore, InMemoryVectorStore

def build_index(store: VectorStore, docs: list[tuple[str, list[float]]]) -> None:
    for doc_id, vec in docs:
        store.upsert(doc_id, vec)

# Works identically with InMemoryVectorStore, FAISSVectorStore, PgVectorStore, or ChromaVectorStore
build_index(InMemoryVectorStore(), [("a", [1.0, 0.0]), ("b", [0.0, 1.0])])
```
