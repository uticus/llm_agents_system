# rag/embeddings

## Overview

The embeddings module converts text strings into fixed-dimensional float vectors that encode semantic meaning. These vectors are the foundation of the entire RAG layer: without them, neither the vector store nor the retriever can operate. The module defines the `Embedder` structural protocol, a `FakeEmbedder` for deterministic testing, a `BatchEmbedder` wrapper that transparently batches large text lists, a `SentenceTransformerEmbedder` for local model inference (requires the `rag` extra), an `OpenAIEmbedder` for the OpenAI embeddings API via an injected client (requires the `openai` extra), and a `CohereEmbedder` for the Cohere embeddings API via an injected client (requires the `cohere` extra).

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `Embedder` | Protocol | Structural interface for text embedding models. |
| `FakeEmbedder` | class | Deterministic test embedder producing unit vectors; tracks call counts. |
| `BatchEmbedder` | class | Wraps any `Embedder` and splits large text lists into fixed-size batches. |
| `SentenceTransformerEmbedder` | class | Local inference via `sentence-transformers`; requires the `rag` extra. |
| `OpenAIEmbedder` | class | OpenAI embeddings API via injected client; requires the `openai` extra. |
| `CohereEmbedder` | class | Cohere embeddings API via injected client; requires the `cohere` extra. |

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

### `SentenceTransformerEmbedder`

```python
class SentenceTransformerEmbedder:
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        *,
        device: str = "cpu",
        normalize_embeddings: bool = True,
    ) -> None: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimensions(self) -> int: ...  # lazy: loads model on first access

    model_name:           str   # HuggingFace model identifier or local path
    device:               str   # torch device ("cpu", "cuda", "mps")
    normalize_embeddings: bool  # L2-normalise output vectors
```

Requires the `rag` extra (`sentence-transformers` package). The model is loaded lazily on first
access to `dimensions` or `embed()`. `ImportError` is raised at that point if the package is not
installed. The loaded model is cached for the lifetime of the instance.

### `OpenAIEmbedder`

```python
class OpenAIEmbedder:
    def __init__(
        self,
        client,
        model: str = "text-embedding-3-small",
        *,
        dimensions: int | None = None,
    ) -> None: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimensions(self) -> int: ...  # raises ValueError if unknown

    model: str  # OpenAI model name
```

Requires an injected OpenAI-compatible client; `openai` is never imported by this module.
`dimensions` is forwarded to the API when set (Matryoshka truncation for `text-embedding-3-*`
models). If omitted, `dimensions` is inferred from the first response and raises `ValueError`
if read before any `embed()` call.

### `CohereEmbedder`

```python
class CohereEmbedder:
    def __init__(
        self,
        client,
        model: str = "embed-english-v3.0",
        *,
        input_type: str = "search_document",
        dimensions: int | None = None,
    ) -> None: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimensions(self) -> int: ...  # raises ValueError if unknown

    model:      str  # Cohere model name
    input_type: str  # forwarded to every embed() call
```

Requires an injected Cohere client; `cohere` is never imported by this module.
`input_type` is required by Cohere v3+ models and distinguishes indexing-time document vectors
(`"search_document"`) from query-time vectors (`"search_query"`).  `dimensions` is inferred
from the first response when omitted and raises `ValueError` if read before then.

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
      +---> SentenceTransformerEmbedder  (rag extra, local inference)
      +---> OpenAIEmbedder               (openai extra, injected client)
      +---> CohereEmbedder               (cohere extra, injected client)
      +---> FakeEmbedder                 (built-in, deterministic, for tests)
      +---> <any class with dimensions + embed()>
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

**`SentenceTransformerEmbedder`** wraps `sentence_transformers.SentenceTransformer` with lazy model loading. The model is only instantiated on the first call to `embed()` or `dimensions`, so the module is importable without the extra installed. `dimensions` is cached after the first access. `normalize_embeddings=True` (default) ensures vectors are L2-normalised so cosine similarity equals dot product.

**`OpenAIEmbedder`** takes an injected client and never imports `openai` itself. `dimensions` can be supplied at construction time (forwarded to the API for Matryoshka-style truncation on `text-embedding-3-*` models) or inferred from the first response. Accessing `dimensions` before any `embed()` call without a constructor value raises `ValueError`.

**`CohereEmbedder`** takes an injected client and never imports `cohere` itself. `input_type` is forwarded on every call — use `"search_document"` when embedding corpus chunks and `"search_query"` when embedding retrieval queries (both required by Cohere v3+ models for asymmetric search). `dimensions` follows the same lazy-inference pattern as `OpenAIEmbedder`.

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

- **Decision**: `SentenceTransformerEmbedder` and `OpenAIEmbedder` use deferred/injected dependencies — no imports at module level.
  **Why**: Keeps the module importable without optional extras. Tests can mock the underlying model/client with plain MagicMock; no real network or GPU required.
  **Tradeoff**: If the extra is not installed, errors are raised at first use, not at import time. Callers who want an early check should call `emb.dimensions` right after construction.

- **Decision**: `OpenAIEmbedder` raises `ValueError` on `dimensions` access before first `embed()` when no `dimensions=` was passed.
  **Why**: Returning a sentinel like `0` would silently mislead vector store constructors. Raising is honest about the unknown state.
  **Tradeoff**: Code that reads `embedder.dimensions` at construction time must either pass `dimensions=` or call `embed([""])` first.

---

## Scaling concerns

- **Batch size**: The default `batch_size=32` in `BatchEmbedder` is conservative. Sentence-transformer models typically handle 64–256 texts per batch efficiently on GPU. Provider APIs may have separate per-request and per-minute token limits that require tuning both `batch_size` and concurrency.
- **Concurrency**: `embed` is synchronous. For high-throughput indexing, the `Indexer` should wrap the embedder call in `asyncio.get_event_loop().run_in_executor` so that embedding does not block the event loop while waiting for a GPU or network response.
- **Memory**: Each call to `embed` with a large batch allocates a new `list[list[float]]`. For 1 000 chunks at 1 536 dimensions (OpenAI ada-002 size), this is roughly 12 MB of Python list objects per call.
- **Model loading latency**: Local sentence-transformer models take several seconds to load from disk. The model should be loaded once at application startup and reused, not instantiated per request.

---

## Future improvements

- **Async embed interface**: Add an `AsyncEmbedder` protocol variant with `async def embed(...)` for provider API calls so they can be properly awaited without blocking the event loop.
- **Asymmetric search helper**: `CohereEmbedder` requires the caller to manage `input_type` manually; a convenience wrapper that automatically sets `"search_document"` vs `"search_query"` based on context would reduce error surface.
- **Dimension validation**: Add a runtime check in `Indexer` and `DenseRetriever` that the embedder's `dimensions` matches the vector store's expected dimension, raising a clear error at construction time rather than a cryptic shape mismatch later.
- **Caching layer**: Add an optional `CachingEmbedder` wrapper that memoises vectors by text hash, avoiding redundant API calls for frequently recurring chunks.
- **Retry + rate-limit logic**: `OpenAIEmbedder` currently makes a single API call. A production wrapper should add exponential back-off on 429/503 and respect per-minute token limits.

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

**SentenceTransformerEmbedder (local inference):**

```python
# Requires: pip install 'llm-agents-system[rag]'
from llm_agents.rag.embeddings import SentenceTransformerEmbedder

embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2", device="cpu")
# Model is loaded lazily on first use:
vectors = embedder.embed(["The cat sat on the mat.", "Dogs are great."])
print(embedder.dimensions)   # 384 for all-MiniLM-L6-v2
print(len(vectors))          # 2
print(len(vectors[0]))       # 384
```

**OpenAIEmbedder (provider API):**

```python
# Requires: pip install 'llm-agents-system[openai]'
import openai
from llm_agents.rag.embeddings import OpenAIEmbedder

client = openai.OpenAI()   # reads OPENAI_API_KEY from environment

# Pass dimensions= to use Matryoshka truncation (text-embedding-3-* only):
embedder = OpenAIEmbedder(client, model="text-embedding-3-small", dimensions=512)
vectors = embedder.embed(["Hello, world!", "Another document."])
print(embedder.dimensions)   # 512
print(len(vectors[0]))       # 512

# Without dimensions=, it is inferred from the first response:
embedder2 = OpenAIEmbedder(client)
vectors2 = embedder2.embed(["test"])
print(embedder2.dimensions)  # 1536 (text-embedding-3-small default)
```

**CohereEmbedder (provider API):**

```python
# Requires: pip install 'llm-agents-system[cohere]'
import cohere
from llm_agents.rag.embeddings import CohereEmbedder

co = cohere.Client(api_key="...")

# Index-time: use input_type="search_document"
doc_embedder = CohereEmbedder(co, model="embed-english-v3.0", input_type="search_document")
doc_vectors = doc_embedder.embed(["Paris is the capital of France.", "Dogs are great."])
print(doc_embedder.dimensions)   # inferred from response (e.g. 1024)

# Query-time: use input_type="search_query"
query_embedder = CohereEmbedder(co, model="embed-english-v3.0", input_type="search_query")
query_vector = query_embedder.embed(["capital of France"])[0]
```
