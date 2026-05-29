# rag/retrieval

## Overview

The retrieval module implements dense passage retrieval: given a natural-language query string, it produces a ranked list of text chunks from the vector store that are semantically similar to the query. It does this by embedding the query with the same `Embedder` used at index time, querying the `VectorStore` for the nearest vectors, and wrapping each result in a `RetrievedPassage` dataclass. An optional metadata filtering step allows callers to restrict results to passages from a specific document source, date range, or any other structured attribute stored at index time. The module's output (`list[RetrievedPassage]`) is the primary input to the reranking and pipeline modules.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `RetrievedPassage` | dataclass | A passage returned from retrieval: doc_id, text, score, metadata. |
| `DenseRetriever` | class | Embeds the query and searches the vector store; applies optional metadata filters. |

### `RetrievedPassage`

```python
@dataclass
class RetrievedPassage:
    doc_id:   str
    text:     str = ""
    score:    float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
```

`doc_id` holds the chunk ID as stored in the vector store (e.g. `"mydoc#3"`). `text` is populated from `metadata["text"]` if that key exists; otherwise it is an empty string. `score` is the cosine similarity returned by the vector store. `metadata` is a copy of the stored chunk metadata.

### `DenseRetriever`

```python
class DenseRetriever:
    def __init__(
        self,
        embedder:     Any,          # satisfies Embedder protocol
        vector_store: Any,          # satisfies VectorStore protocol
        top_k:        int = 5,
    ) -> None: ...

    def retrieve(
        self,
        query:   str,
        *,
        top_k:   int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedPassage]: ...

    top_k: int
```

`top_k` on the constructor sets the default; the per-call `top_k` overrides it. Raises `ValueError` if the constructor `top_k < 1`.

---

## Architecture

### Conceptual view

```
query: str
       |
       v
  embedder.embed([query]) -> [[float, ...]]
       |
       v  query_vector
  vector_store.search(query_vector, top_k=k)
       |
       v  list[SearchResult]
  [metadata filter]  (if filters != None)
       |
       v  list[SearchResult] after filter
  map each to RetrievedPassage(
      doc_id   = result.doc_id,
      text     = result.metadata.get("text", ""),
      score    = result.score,
      metadata = result.metadata,
  )
       |
       v
  list[RetrievedPassage]  (sorted by descending score, inherited from VectorStore)
```

### Data flow

1. `retrieve(query, top_k=k, filters=filters)` is called.
2. `embedder.embed([query])` is called with a single-element list; the first element of the returned list is the query vector.
3. `vector_store.search(query_vector, top_k=k)` is called, returning at most `k` `SearchResult` objects in descending score order.
4. For each `SearchResult`:
   - If `filters` is not `None`, `_matches(result.metadata, filters)` is evaluated. Results that do not match all key-value pairs are excluded.
   - The result is converted to a `RetrievedPassage`. The `text` field is populated from `result.metadata.get("text", "")`.
5. The filtered, converted list is returned. Note: the effective number of results may be less than `top_k` after filtering.

### Key abstractions

**`RetrievedPassage`** exists to decouple the retriever's output from the vector store's internal `SearchResult`. `SearchResult` is a low-level store concept (doc_id + score + metadata). `RetrievedPassage` is a higher-level concept oriented towards the LLM consumer: it has a `text` field that the generator will include in a prompt. This separation means the vector store does not need to know anything about text or language.

**Metadata filtering (`_matches`)** is a post-retrieval operation. This is simpler than pre-filtering at the vector store level, which not all backends support efficiently. The downside is that requesting `top_k=10` with a selective filter may yield far fewer than 10 results. Callers that need exactly `top_k` filtered results must request a larger `top_k` and trim the output.

**`embedder.embed([query])`** wraps the single query in a list because the `Embedder` protocol is batch-oriented. This ensures the retriever is compatible with any conforming embedder without needing a separate `embed_one` method.

---

## Design decisions and tradeoffs

- **Decision**: Retrieve text from `metadata["text"]` rather than maintaining a separate text store.
  **Why**: Keeps the architecture simple — a single store holds both vectors and their source text. No secondary lookup is needed.
  **Tradeoff**: Every chunk's text must be stored in the metadata dict at index time. For large corpora, this doubles the storage requirement (vector + text) compared to storing text in a separate document store. The `Indexer` module currently does not automatically store `"text"` in metadata; callers must include it explicitly.

- **Decision**: Metadata filtering is applied post-search (after the vector store returns results).
  **Why**: Works with any `VectorStore` implementation, even those with no native metadata filtering support.
  **Tradeoff**: The effective `top_k` may be lower than requested. If the filter is very selective, the caller must over-fetch (large `top_k`) to get enough results, increasing retrieval latency.

- **Decision**: `retrieve` is synchronous.
  **Why**: Consistent with the synchronous `embed` and `search` methods it calls.
  **Tradeoff**: Blocks the calling thread/event loop during embedding (which may involve a network call to a provider API) and during store search.

- **Decision**: `top_k` is overridable per call.
  **Why**: Different use cases in the same application (question answering vs. document summarisation vs. citation) may need different numbers of passages. A per-call override avoids creating separate retriever instances.
  **Tradeoff**: Per-call overrides add two branching paths (constructor default vs. call-site value) that must both be tested.

- **Decision**: Score order is inherited from the vector store (descending cosine similarity), not re-sorted by the retriever.
  **Why**: Avoids redundant sorting; the store is already responsible for ordering.
  **Tradeoff**: If a different scoring metric is used (e.g. BM25 hybrid), the retriever cannot guarantee ordering without re-sorting.

---

## Scaling concerns

- **Embedding latency**: `embedder.embed([query])` is called synchronously. For provider embeddings (OpenAI, Cohere), this is a network call. Under high query throughput, concurrent requests will block event loop workers. An async retriever with `await embedder.embed(...)` is needed for production serving.
- **Vector store search cost**: `InMemoryVectorStore.search` is O(n) in the number of stored vectors. At production scale (millions of vectors), this must be replaced with an approximate nearest-neighbour backend.
- **Post-filtering inefficiency**: When `filters` removes most results, the vector store is asked to do work that is largely wasted. Native metadata filtering support (Weaviate, Chroma, Elasticsearch) should be preferred over post-filtering for selective queries.
- **Single query embedding**: `embed([query])` initiates a round-trip to the model for every `retrieve` call. Batching multiple queries into a single `embed` call (where the caller knows the queries in advance) would be more efficient.

---

## Future improvements

- **Async `retrieve`**: Make `retrieve` an async method so that embedding and vector search can be awaited without blocking.
- **Pre-filter support**: Add a `VectorStore.search_with_filter(query_vector, top_k, filters)` optional method so adapters that support native metadata filtering (Weaviate, Chroma, Elasticsearch) can be exploited.
- **Hybrid retrieval**: Combine dense retrieval scores with sparse BM25 scores (Reciprocal Rank Fusion or linear interpolation). This typically improves precision on factoid queries.
- **Text storage in index**: Update `Indexer` to automatically store `"text"` in chunk metadata so the retriever always has the chunk text available without callers needing to remember to pass it.
- **Query expansion**: Add an optional `query_expander` callable that rewrites or expands the query before embedding (e.g. HyDE — Hypothetical Document Embeddings), improving recall for sparse or ambiguous queries.

---

## Usage examples

**Basic retrieval:**

```python
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.retrieval import DenseRetriever

embedder = FakeEmbedder(dimensions=4)
store = InMemoryVectorStore()
store.upsert("doc-1#0", [1.0, 0.0, 0.0, 0.0], metadata={"text": "Python is great", "source": "wiki"})
store.upsert("doc-2#0", [0.0, 1.0, 0.0, 0.0], metadata={"text": "Go is fast", "source": "blog"})

retriever = DenseRetriever(embedder=embedder, vector_store=store, top_k=2)
passages = retriever.retrieve("what programming language?")
for p in passages:
    print(p.doc_id, p.score, p.text)
```

**Retrieval with metadata filters:**

```python
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.retrieval import DenseRetriever

embedder = FakeEmbedder(dimensions=4)
store = InMemoryVectorStore()
store.upsert("wiki#0", [1.0, 0.0, 0.0, 0.0], metadata={"text": "Wiki article", "source": "wiki"})
store.upsert("blog#0", [1.0, 0.0, 0.0, 0.0], metadata={"text": "Blog post", "source": "blog"})

retriever = DenseRetriever(embedder=embedder, vector_store=store)
# Only return passages from the wiki source
passages = retriever.retrieve("query", filters={"source": "wiki"})
assert all(p.metadata["source"] == "wiki" for p in passages)
```

**Per-call top_k override:**

```python
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.retrieval import DenseRetriever

embedder = FakeEmbedder(dimensions=4)
store = InMemoryVectorStore()
for i in range(20):
    store.upsert(f"doc-{i}#0", [1.0, 0.0, 0.0, 0.0], metadata={"text": f"chunk {i}"})

retriever = DenseRetriever(embedder=embedder, vector_store=store, top_k=5)
passages_10 = retriever.retrieve("query", top_k=10)
assert len(passages_10) == 10
```
