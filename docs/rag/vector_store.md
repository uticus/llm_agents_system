# rag/vector_store

## Overview

The vector store module provides persistent (or in-process) storage for embedding vectors and associated metadata, along with similarity search over those vectors. It is the core index that makes retrieval-augmented generation possible: at indexing time, chunk embeddings are written into the store; at retrieval time, a query embedding is used to find the nearest stored vectors. The module defines the `VectorStore` structural protocol, a `SearchResult` dataclass for query results, and an `InMemoryVectorStore` implementation backed by a plain Python dict with brute-force cosine similarity computation. Production deployments are expected to swap in FAISS, pgvector, Weaviate, Chroma, or Elasticsearch adapters behind the same protocol.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `SearchResult` | dataclass | Single result from a vector search: doc_id, score, metadata. |
| `VectorStore` | Protocol | Structural interface for vector stores: upsert, search, delete. |
| `InMemoryVectorStore` | class | Brute-force in-memory store with cosine similarity; for tests and prototyping. |

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

---

## Architecture

### Conceptual view

```
   [ Indexer ]
        |
        | upsert(chunk_id, vector, metadata)
        v
  +-----------------+
  | VectorStore     |  <-- Protocol
  |  upsert         |
  |  search         |
  |  delete         |
  +-----------------+
        ^
        | search(query_vector, top_k)
        |
   [ DenseRetriever ]
```

The vector store sits at the centre of the RAG data plane. Writes come from the `Indexer`; reads come from the `DenseRetriever`. Neither component depends on the concrete implementation, only on the `VectorStore` protocol.

### Data flow

**Write path (indexing):**
1. `Indexer` calls `store.upsert(chunk_id, vector, metadata)`.
2. `InMemoryVectorStore` copies the vector and metadata into a `_Entry` and stores it under `chunk_id`.
3. If the key already exists, the old entry is replaced (idempotent upsert).

**Read path (retrieval):**
1. `DenseRetriever` calls `store.search(query_vector, top_k=k)`.
2. `InMemoryVectorStore` computes cosine similarity between `query_vector` and every stored vector.
3. Results are collected into `SearchResult` objects, sorted descending, and the top `k` are returned.

**Delete path:**
1. Caller calls `store.delete(doc_id)`.
2. Returns `True` if the entry existed and was removed, `False` otherwise.

### Key abstractions

**`SearchResult`** separates the vector store's view of a result (doc_id + score + metadata) from the retrieval layer's view (`RetrievedPassage` with text). The vector store does not know what text a chunk contains; it only knows vectors and metadata. The mapping from chunk_id back to text is done by the retriever, which looks for a `"text"` key in `metadata`.

**`VectorStore` Protocol** enforces three operations: write (upsert), read (search), and delete. Delete is included because production RAG systems must be able to remove stale or retracted documents. The protocol deliberately excludes bulk operations and persistence management to keep it minimal.

**`InMemoryVectorStore`** internal `_cosine` function handles the zero-norm edge case (returns 0.0 for zero vectors) and uses `zip(a, b, strict=False)` so mismatched-length vectors do not raise but silently compute a partial dot product — callers are responsible for dimension consistency.

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

---

## Scaling concerns

- **O(n) search**: `InMemoryVectorStore.search` computes cosine similarity against every stored vector. At 10 000 vectors this is fast; at 1 000 000 vectors it is completely impractical. The threshold for switching to an approximate nearest-neighbour backend (FAISS, Weaviate, pgvector HNSW) is roughly 10 000–50 000 vectors depending on latency requirements.
- **Memory footprint**: Each stored vector of dimension `d` costs approximately `8d` bytes (Python float is 8 bytes) plus dict and object overhead. At 1 536 dimensions (OpenAI ada-002), one million vectors cost approximately 12 GB in pure Python lists.
- **Concurrency**: `InMemoryVectorStore` is not thread-safe. Concurrent upsert and search operations on the same instance can produce incorrect results. Thread safety requires either a lock or a dedicated thread-safe data structure.
- **No persistence**: `InMemoryVectorStore` loses all data on process exit. All production use cases require a persistent backend.

---

## Future improvements

- **FAISS adapter**: Add a `FaissVectorStore` in the `rag` optional extra that wraps a FAISS `IndexFlatIP` (inner product / cosine on normalised vectors) or `IndexHNSWFlat` for approximate search.
- **pgvector adapter**: Add a `PgVectorStore` that uses `asyncpg` or `psycopg3` to store vectors in PostgreSQL with the `pgvector` extension, enabling persistent storage with full SQL metadata filtering.
- **Weaviate / Chroma adapters**: Add adapters for managed vector database services with native metadata filtering, authentication, and horizontal scaling.
- **Bulk upsert**: Add an `upsert_batch(entries: list[tuple[str, list[float], dict]]) -> None` method to the protocol for efficient bulk loading, which most production backends support natively.
- **Dimension enforcement**: Store the expected dimension at construction time and validate every upserted vector, raising a descriptive error on mismatch rather than silently computing wrong similarity scores.

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
