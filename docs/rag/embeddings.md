# rag/embeddings

## Overview

The embeddings module converts text strings into fixed-dimensional float vectors that encode semantic meaning. These vectors are the foundation of the entire RAG layer: without them, neither the vector store nor the retriever can operate. The module defines the `Embedder` structural protocol, a `FakeEmbedder` for deterministic testing, and a `BatchEmbedder` wrapper that transparently batches large text lists into smaller calls to any underlying embedder. Concrete model-backed implementations (sentence-transformers for local inference, OpenAI or Cohere for provider embeddings) are intended to live behind this protocol as optional-extra adapters.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `Embedder` | Protocol | Structural interface for text embedding models. |
| `FakeEmbedder` | class | Deterministic test embedder producing unit vectors; tracks call counts. |
| `BatchEmbedder` | class | Wraps any `Embedder` and splits large text lists into fixed-size batches. |

### `Embedder` Protocol

```python
@runtime_checkable
class Embedder(Protocol):
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

Any object with a `dimensions: int` attribute and a matching `embed` method satisfies the protocol. The protocol is `@runtime_checkable` so `isinstance(obj, Embedder)` works at runtime.

### `FakeEmbedder`

```python
class FakeEmbedder:
    def __init__(self, dimensions: int = 4) -> None: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    dimensions:   int    # set at construction
    embed_count:  int    # incremented on every embed() call
    total_texts:  int    # cumulative count of individual texts embedded
```

Each returned vector is `[1.0, 0.0, 0.0, ...]` — a unit vector along the first axis, regardless of input text. Raises `ValueError` if `dimensions < 1`.

### `BatchEmbedder`

```python
class BatchEmbedder:
    def __init__(self, embedder: Any, batch_size: int = 32) -> None: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimensions(self) -> int: ...  # delegates to wrapped embedder

    batch_size: int
```

Raises `ValueError` if `batch_size < 1`. Results are returned in the same order as the input texts.

---

## Architecture

### Conceptual view

```
 [ Indexer ]         [ DenseRetriever ]
      |                     |
      | embed(chunks)       | embed([query])
      v                     v
 [ BatchEmbedder ]   <-- optional wrapper
      |
      v
 [ Embedder ]   <-- Protocol
      |
      v (concrete implementations, optional extras)
 sentence-transformers / OpenAI API / Cohere API / ...
```

The embedder is consumed in two places: by the `Indexer` (to embed document chunks at index time) and by the `DenseRetriever` (to embed the query at retrieval time). Both call `embed(list[str])` and receive `list[list[float]]`.

### Data flow

**At index time (Indexer path):**
1. `Indexer.index(doc_id, text)` calls `chunker(text)` to split text into chunks.
2. New chunks are collected into a list and passed to `embedder.embed(texts)` in a single batch call.
3. Resulting vectors are upserted into the vector store paired with chunk IDs.

**At query time (DenseRetriever path):**
1. `DenseRetriever.retrieve(query)` calls `embedder.embed([query])`.
2. The single returned vector is used as the query for `VectorStore.search`.

**BatchEmbedder intermediary:**
1. `BatchEmbedder.embed(texts)` splits `texts` into slices of at most `batch_size`.
2. Each slice is passed to the wrapped embedder's `embed` method.
3. Results are concatenated and returned in original order.

### Key abstractions

**`Embedder` Protocol** fixes the contract at `dimensions: int` and `embed(list[str]) -> list[list[float]]`. The `dimensions` attribute is required because downstream components (vector stores, similarity functions) need to know vector size at construction time, independent of any actual text input.

**`FakeEmbedder`** produces a unit vector along the first axis. This choice makes all vectors identical, which simplifies assertions in tests: cosine similarity between any two fake vectors is always 1.0 (parallel unit vectors). The `embed_count` and `total_texts` counters enable tests to verify that batching and call patterns are correct without inspecting the vector values themselves.

**`BatchEmbedder`** is a pure wrapper that adds no semantic transformation. It exists because real embedding models impose per-request token and item count limits. Decoupling batch management from the model implementation keeps individual model adapters simple.

---

## Design decisions and tradeoffs

- **Decision**: `embed` accepts `list[str]` and returns `list[list[float]]`, not numpy arrays or tensors.
  **Why**: Plain Python lists require no external dependencies and are easily serialisable. The protocol stays importable even when numpy or PyTorch are not installed.
  **Tradeoff**: For large batches, converting from numpy arrays to lists (and back) adds overhead. High-performance adapters will want to work with arrays internally and only convert at the protocol boundary.

- **Decision**: `FakeEmbedder` produces a constant vector regardless of input text.
  **Why**: Determinism is more important than realism in unit tests. A constant output makes test assertions trivial.
  **Tradeoff**: `FakeEmbedder` cannot be used to test retrieval quality or ranking behaviour because all vectors are identical; a `RandomEmbedder` with a fixed seed would be needed for such tests.

- **Decision**: `BatchEmbedder` is a separate class rather than a method on `Embedder`.
  **Why**: Keeps the protocol minimal (one method) and allows batching to be composed in or out at the call site. Some embedders (e.g. provider APIs) handle batching internally and do not need the wrapper.
  **Tradeoff**: Callers must explicitly wrap their embedder with `BatchEmbedder` if they want batching; it is not automatic.

- **Decision**: `dimensions` is an instance attribute, not a method.
  **Why**: Dimensionality is a static property of a model, not a function of input. Making it an attribute signals this and allows type checkers and container constructors to read it without calling a method.
  **Tradeoff**: Embedders whose dimensionality depends on runtime configuration (unusual but possible) must compute it at `__init__` time and store it.

---

## Scaling concerns

- **Batch size**: The default `batch_size=32` in `BatchEmbedder` is conservative. Sentence-transformer models typically handle 64–256 texts per batch efficiently on GPU. Provider APIs may have separate per-request and per-minute token limits that require tuning both `batch_size` and concurrency.
- **Concurrency**: `embed` is synchronous. For high-throughput indexing, the `Indexer` should wrap the embedder call in `asyncio.get_event_loop().run_in_executor` so that embedding does not block the event loop while waiting for a GPU or network response.
- **Memory**: Each call to `embed` with a large batch allocates a new `list[list[float]]`. For 1 000 chunks at 1 536 dimensions (OpenAI ada-002 size), this is roughly 12 MB of Python list objects per call.
- **Model loading latency**: Local sentence-transformer models take several seconds to load from disk. The model should be loaded once at application startup and reused, not instantiated per request.

---

## Future improvements

- **Async embed interface**: Add an `AsyncEmbedder` protocol variant with `async def embed(...)` for provider API calls so they can be properly awaited without blocking the event loop.
- **Sentence-transformers adapter**: Ship a `SentenceTransformerEmbedder` in the `rag` optional extra that wraps `sentence_transformers.SentenceTransformer` and exposes the standard `Embedder` protocol.
- **Provider adapters**: Add `OpenAIEmbedder` and `CohereEmbedder` as thin wrappers behind the protocol, handling API key management, retry logic, and rate limiting.
- **Dimension validation**: Add a runtime check in `Indexer` and `DenseRetriever` that the embedder's `dimensions` matches the vector store's expected dimension, raising a clear error at construction time rather than a cryptic shape mismatch later.
- **Caching layer**: Add an optional `CachingEmbedder` wrapper that memoises vectors by text hash, avoiding redundant API calls for frequently recurring chunks.

---

## Usage examples

**FakeEmbedder in a test:**

```python
from llm_agents.rag.embeddings import FakeEmbedder

embedder = FakeEmbedder(dimensions=8)
vectors = embedder.embed(["hello", "world"])
assert len(vectors) == 2
assert len(vectors[0]) == 8
assert embedder.embed_count == 1
assert embedder.total_texts == 2
```

**BatchEmbedder wrapping a real or fake embedder:**

```python
from llm_agents.rag.embeddings import BatchEmbedder, FakeEmbedder

base = FakeEmbedder(dimensions=4)
batched = BatchEmbedder(embedder=base, batch_size=3)

texts = [f"text {i}" for i in range(10)]
vectors = batched.embed(texts)
assert len(vectors) == 10
# base.embed was called ceil(10/3) = 4 times
assert base.embed_count == 4
```

**Runtime protocol check:**

```python
from llm_agents.rag.embeddings import Embedder, FakeEmbedder, BatchEmbedder

embedder = FakeEmbedder(dimensions=16)
assert isinstance(embedder, Embedder)

batched = BatchEmbedder(embedder=embedder, batch_size=8)
assert isinstance(batched, Embedder)
```
