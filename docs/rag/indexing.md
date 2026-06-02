# rag/indexing

## Overview

The indexing module bridges the data ingestion tier and the vector retrieval tier by taking parsed document text, splitting it into chunks, embedding those chunks, and writing the resulting vectors into a vector store. It exposes a single `Indexer` class that composes a chunker callable, an `Embedder`, and a `VectorStore` into a unified `index(doc_id, text)` entry point. A key design property is idempotency: chunk IDs are derived deterministically from `doc_id` and chunk position, and content hashes are maintained across calls so unchanged chunks are never re-embedded or re-upserted. The `IndexReport` dataclass provides per-run statistics for observability. This module is the consumer of `rag/embeddings` and `rag/vector_store`, and it is fed by `data/ingestion` (via the `upsert` callback) or called directly.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `Indexer` | class | Chunk -> embed -> upsert pipeline that populates a vector store. |
| `IndexReport` | dataclass | Per-run statistics: docs indexed, chunks added/skipped, errors. |
| `DeduplicationStore` | Protocol | Interface for pluggable content-hash deduplication backends. |
| `InMemoryDeduplicationStore` | class | Default in-memory dedup store (state lost on restart). |
| `SQLiteDeduplicationStore` | class | Durable SQLite-backed dedup store (state persists across restarts). |

### `IndexReport`

```python
@dataclass
class IndexReport:
    docs_indexed:   int = 0
    chunks_added:   int = 0
    chunks_skipped: int = 0
    errors:         list[str] = field(default_factory=list)
```

`errors` contains strings of the form `"<doc_id>: embed error — <exception>"` when the embedder raises.

### `Indexer`

```python
class Indexer:
    def __init__(
        self,
        embedder:     Any,           # satisfies Embedder protocol
        vector_store: Any,           # satisfies VectorStore protocol
        chunker:      Any = None,    # Callable[[str], list[str]]; default: identity
        *,
        dedup_store:  DeduplicationStore | None = None,
    ) -> None: ...

    def index(
        self,
        doc_id:   str,
        text:     str,
        metadata: dict[str, Any] | None = None,
    ) -> IndexReport: ...

    def index_batch(
        self,
        documents: list[tuple[str, str]],
        metadata:  dict[str, Any] | None = None,
    ) -> IndexReport: ...

    @property
    def seen_count(self) -> int: ...    # unique chunk-content hashes accumulated
    def reset_dedup(self) -> None: ...  # clear the dedup store
```

The default `chunker` is `lambda text: [text]` — the entire document text becomes one chunk. The `metadata` dict passed to `index` is merged into every chunk's stored metadata alongside the automatically added `"doc_id"` and `"chunk_index"` keys.

`dedup_store` is keyword-only. When `None` (the default), an `InMemoryDeduplicationStore` is created internally — identical behaviour to before this parameter existed.

### `DeduplicationStore`, `InMemoryDeduplicationStore`, `SQLiteDeduplicationStore`

See [`data/ingestion` — Public API](../data/ingestion.md#public-api) for full API descriptions. The same three classes are re-exported from `rag/indexing` for caller convenience.

---

## Architecture

### Conceptual view

```
   text (str)
        |
        v
   chunker(text) -> list[str]
        |
        v  filter already-seen chunks (content hash)
   new_chunks: list[(idx, str)]
        |
        v  single batch call
   embedder.embed([chunk_text, ...]) -> list[list[float]]
        |
        v  zip (idx, chunk) with vector
   for each (idx, chunk, vector):
       chunk_id = "<doc_id>#<idx>"
       vector_store.upsert(chunk_id, vector, metadata)
        |
        v
   IndexReport
```

### Data flow

1. `index(doc_id, text, metadata)` calls `chunker(text)` to get a list of chunk strings.
2. Each chunk is hashed with MD5. Chunks whose hash is already in `dedup_store` are counted as `chunks_skipped` and excluded.
3. The remaining new chunks are embedded in a single `embedder.embed(texts)` call (minimising round-trips to GPU or API).
4. For each `(idx, chunk)` and its corresponding vector:
   - A stable chunk ID `"<doc_id>#<idx>"` is computed.
   - `vector_store.upsert(chunk_id, vector, chunk_meta)` is called where `chunk_meta` includes the caller-supplied `metadata` plus `"doc_id"` and `"chunk_index"`.
   - The content hash is added to `_seen_hashes`.
5. An `IndexReport` is returned.
6. `index_batch(documents)` calls `index` for each `(doc_id, text)` tuple and aggregates the reports.

### Key abstractions

**Deterministic chunk IDs** (`"<doc_id>#<chunk_index>"`) ensure that re-indexing the same document produces the same IDs, so the vector store performs an idempotent upsert rather than creating duplicate entries. This is critical for correctness when content is updated: the old vector is simply replaced in-place.

**Content-hash deduplication** (`dedup_store`) operates at the chunk level, unlike `IngestionPipeline` which deduplicates at the document level. A chunk is skipped only if its exact text has been seen before. This means partial document updates — where only some chunks change — still re-embed the changed chunks while skipping unchanged ones.

**Single-batch embed call** per `index` invocation is a deliberate performance optimisation. Collecting all new chunks for a document before calling the embedder reduces the number of model forward passes and, for provider APIs, reduces the number of HTTP round-trips.

---

## Design decisions and tradeoffs

- **Decision**: Chunk ID format is `"<doc_id>#<chunk_index>"` (a simple string concatenation with `#` as separator).
  **Why**: Simple, human-readable, and stable. The `#` character is uncommon in typical `doc_id` values.
  **Tradeoff**: If a `doc_id` itself contains `#`, the chunk ID is ambiguous. Production use should sanitise or escape `doc_id` values.

- **Decision**: All new chunks for a single document are embedded in one batch call.
  **Why**: Minimises embedder overhead (GPU kernel launches, API request count). Most documents have fewer chunks than the `BatchEmbedder` batch size, so this is effectively free batching.
  **Tradeoff**: If a single document has thousands of chunks (a very large document), the single batch call may exceed the embedder's per-request size limit. The caller must either pre-configure `BatchEmbedder` or split very large documents before calling `index`.

- **Decision**: Content hash deduplication is per-chunk (not per-document as in `IngestionPipeline`), managed by a pluggable `DeduplicationStore`.
  **Why**: Enables partial re-indexing: only changed chunks of an updated document are re-embedded, while unchanged chunks are skipped. The pluggable store allows callers to choose between in-memory (fast, session-scoped) and SQLite-backed (durable, survives restarts).
  **Tradeoff**: Two different documents could produce identical chunks (e.g. a boilerplate header). The second occurrence would be skipped by the dedup check even though it should produce an entry under a different chunk ID. This is a correctness edge case worth addressing.

- **Decision**: `metadata` is merged with auto-generated `"doc_id"` and `"chunk_index"` keys and stored alongside each vector.
  **Why**: The retriever needs `"doc_id"` to map chunk results back to the originating document. `"chunk_index"` enables ordered reconstruction of the original document from its chunks.
  **Tradeoff**: Caller-supplied metadata keys `"doc_id"` or `"chunk_index"` would be silently overwritten by the auto-generated values.

- **Decision**: Embed errors are caught and recorded in `report.errors` rather than raising.
  **Why**: Consistent with the error-accumulation pattern used throughout the data and RAG tiers; a single failed embed should not abort a batch of thousands.
  **Tradeoff**: The chunks from a failed document are not indexed; retrieval will silently return no results for those chunks.

---

## Scaling concerns

- **Batch indexing throughput**: `index_batch` calls `index` sequentially. For large document sets, parallel indexing with a concurrency limit (e.g. using `asyncio.gather` with a semaphore) would substantially increase throughput.
- **Memory** (in-memory store): `InMemoryDeduplicationStore` grows with every unique chunk indexed. At one million unique chunks (32-byte hex strings each), this is approximately 32 MB. For very long-running processes, `reset_dedup()` or instance rotation is needed. `SQLiteDeduplicationStore` offloads this to disk; `Indexer` calls `add_batch` once per document so the cost is one SQLite transaction per document, not one per chunk.
- **Vector store write throughput**: Each chunk triggers one `vector_store.upsert` call. For `InMemoryVectorStore`, this is fast. For remote stores (pgvector, Weaviate), each call involves a network round-trip. A `upsert_batch` method on the vector store would dramatically reduce write latency.
- **Chunker quality**: The default identity chunker produces one vector per document, which is appropriate only for short texts. For longer texts, retrieval precision degrades because a single large chunk is less topically focused than smaller ones. A fixed-size or sentence-boundary chunker is required for production.

---

## Future improvements

- **Async `index` method**: Make `index` and `index_batch` async so that embedder and vector store calls can be awaited, enabling non-blocking operation in an async application server.
- **Configurable chunk ID strategy**: Accept a `chunk_id_fn: Callable[[str, int], str]` parameter so callers can supply their own chunk ID scheme (e.g. UUID-based or content-hash-based IDs).
- **Smarter chunkers**: Provide built-in chunker implementations — fixed-size with overlap, sentence-boundary (using spaCy or NLTK), and markdown-section-aware — as optional-extra utilities.
- **Bulk vector store writes**: When the vector store supports bulk upsert, collect all chunk vectors for a batch and write them in a single call rather than one per chunk.
- **Cross-chunk dedup fix**: Change the dedup key from `content_hash(chunk_text)` to `(doc_id, chunk_index, content_hash(chunk_text))` to avoid incorrectly skipping identical chunks that should appear under different chunk IDs.

---

## Usage examples

**Single-document indexing:**

```python
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.indexing import Indexer

embedder = FakeEmbedder(dimensions=4)
store = InMemoryVectorStore()
indexer = Indexer(embedder=embedder, vector_store=store)

report = indexer.index("doc-1", "The quick brown fox jumped over the lazy dog.")
print(report.docs_indexed, report.chunks_added)  # 1 1
assert "doc-1#0" in store
```

**Batch indexing with a custom chunker:**

```python
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.indexing import Indexer

def sentence_split(text: str) -> list[str]:
    return [s.strip() for s in text.split(".") if s.strip()]

embedder = FakeEmbedder(dimensions=4)
store = InMemoryVectorStore()
indexer = Indexer(embedder=embedder, vector_store=store, chunker=sentence_split)

docs = [
    ("doc-1", "First sentence. Second sentence."),
    ("doc-2", "Another document."),
]
report = indexer.index_batch(docs)
print(report.docs_indexed, report.chunks_added)  # 2 3
```

**Durable deduplication across restarts:**

```python
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.indexing import Indexer, SQLiteDeduplicationStore

# Run 1 — chunk is new; it gets embedded and upserted
store1 = SQLiteDeduplicationStore("index_dedup.db")
indexer1 = Indexer(FakeEmbedder(4), InMemoryVectorStore(), dedup_store=store1)
report1 = indexer1.index("doc-1", "Unique content")
print(report1.chunks_added, report1.chunks_skipped)  # 1 0

# Run 2 (simulating a process restart) — same DB file, same chunk is skipped
store2 = SQLiteDeduplicationStore("index_dedup.db")
indexer2 = Indexer(FakeEmbedder(4), InMemoryVectorStore(), dedup_store=store2)
report2 = indexer2.index("doc-1", "Unique content")
print(report2.chunks_added, report2.chunks_skipped)  # 0 1
```

**Idempotent re-indexing:**

```python
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.indexing import Indexer

embedder = FakeEmbedder(dimensions=4)
store = InMemoryVectorStore()
indexer = Indexer(embedder=embedder, vector_store=store)

indexer.index("doc-1", "Same text")
report2 = indexer.index("doc-1", "Same text")  # re-index same content
print(report2.chunks_skipped)  # 1 — chunk already seen, not re-embedded
```
