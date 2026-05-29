# rag/reranking

## Overview

The reranking module refines the ranked list of passages produced by the retriever before those passages are handed to the generator. Dense retrieval via cosine similarity is fast but imprecise: it ranks passages by approximate vector proximity, which does not always reflect true relevance to the specific query. A reranker applies a second, more expensive scoring step — typically a cross-encoder model that jointly encodes query and passage — to produce a higher-quality ordering. The module defines the `Reranker` structural protocol, a `FakeReranker` for deterministic testing (reverses the list), and a `ScoreReranker` for cases where a caller-supplied scoring function should determine the final order. Production cross-encoder implementations are expected to be plugged in behind the `Reranker` protocol as optional extras.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `Reranker` | Protocol | Structural interface for passage rerankers. |
| `FakeReranker` | class | Deterministic test reranker: reverses passage list and optionally truncates. |
| `ScoreReranker` | class | Sorts passages by a caller-supplied `scorer(query, passage) -> float` callable. |

### `Reranker` Protocol

```python
@runtime_checkable
class Reranker(Protocol):
    def rerank(
        self,
        query:    str,
        passages: list[RetrievedPassage],
        *,
        top_n:    int | None = None,
    ) -> list[RetrievedPassage]:
        ...
```

The protocol is `@runtime_checkable`. Any class with a matching `rerank` method satisfies it. Note the dependency on `RetrievedPassage` from `rag/retrieval`.

### `FakeReranker`

```python
class FakeReranker:
    def __init__(self, top_n: int | None = None) -> None: ...
    def rerank(
        self,
        query:    str,
        passages: list[RetrievedPassage],
        *,
        top_n:    int | None = None,
    ) -> list[RetrievedPassage]: ...

    top_n:         int | None   # constructor default
    rerank_count:  int          # number of rerank() calls
```

The `top_n` at the call site overrides the constructor default when provided. Reversal is applied first; truncation is applied after.

### `ScoreReranker`

```python
class ScoreReranker:
    def __init__(
        self,
        scorer: Any,           # Callable[[str, RetrievedPassage], float]
        top_n:  int | None = None,
    ) -> None: ...

    def rerank(
        self,
        query:    str,
        passages: list[RetrievedPassage],
        *,
        top_n:    int | None = None,
    ) -> list[RetrievedPassage]: ...

    top_n:        int | None
    rerank_count: int
```

`scorer` is called once per passage with `(query, passage)`. Passages are sorted by descending score. Original `passage.score` values are not modified; sorting is purely by the `scorer` output.

---

## Architecture

### Conceptual view

```
DenseRetriever.retrieve(query)
        |
        v  list[RetrievedPassage]  (sorted by cosine similarity)
  [ Reranker ]
        |  rerank(query, passages, top_n=n)
        v  list[RetrievedPassage]  (re-sorted, optionally truncated)
  RagPipeline -> generator
```

The reranker is an optional component in the `RagPipeline`. When `reranker=None` is passed to `RagPipeline`, the retriever's output is forwarded directly to the generator.

### Data flow

**`FakeReranker.rerank(query, passages, top_n=n)`:**
1. Increment `rerank_count`.
2. Determine effective `n`: per-call `top_n` if set, else constructor `top_n`, else keep all.
3. Return `list(reversed(passages))[:n]`.

**`ScoreReranker.rerank(query, passages, top_n=n)`:**
1. Increment `rerank_count`.
2. Determine effective `n`.
3. Call `scorer(query, passage)` for every passage.
4. Sort by scorer output descending.
5. Return `sorted_passages[:n]`.

**Cross-encoder (production pattern):**
1. Construct token pairs `(query, passage.text)` for all passages.
2. Run the cross-encoder model on the entire batch (one forward pass for all pairs).
3. Map output logits to a relevance score.
4. Sort by descending score; truncate to `top_n`.

### Key abstractions

**`Reranker` Protocol** takes `query: str` explicitly rather than a pre-computed query vector. This is because cross-encoders jointly tokenise the query and passage together; they do not operate on pre-computed embeddings. The protocol therefore has a different signature from the bi-encoder path in `Embedder`.

**`FakeReranker`** reverses the list rather than returning it in the original order. This makes tests meaningful: if a test checks that reranking was applied, a no-op reranker (identity) would be indistinguishable from skipping the reranking step entirely. A reverse is distinguishable and requires no model.

**`ScoreReranker`** separates the concern of "how to score a passage" from "how to sort and truncate". The caller provides the scoring logic; `ScoreReranker` handles the mechanics. This enables quick experimentation with custom scoring functions (keyword overlap, BM25, rule-based heuristics) without writing a full reranker class.

---

## Design decisions and tradeoffs

- **Decision**: The `Reranker` protocol takes `list[RetrievedPassage]` directly rather than raw text strings.
  **Why**: `RetrievedPassage` carries `doc_id`, `score`, and `metadata` in addition to `text`. Rerankers may use metadata (e.g. recency, source authority) alongside text to improve ranking.
  **Tradeoff**: The `reranking` module depends on the `retrieval` module's `RetrievedPassage` type, creating a compile-time dependency between these two submodules. A pure string interface would break that dependency at the cost of losing metadata access.

- **Decision**: `top_n` can be set at constructor time and overridden per call.
  **Why**: Provides flexibility without complexity. A `RagPipeline` configured for a specific use case sets the constructor default; individual calls can deviate if needed.
  **Tradeoff**: Two sources of `top_n` (constructor and call) create a priority resolution rule that must be documented and tested for each implementation.

- **Decision**: `ScoreReranker` leaves `passage.score` unchanged.
  **Why**: Preserving the original retrieval score allows downstream components to inspect the original cosine similarity independently of the reranker's judgment.
  **Tradeoff**: The `score` field of a `RetrievedPassage` returned by `ScoreReranker` no longer reflects the ordering, which can be confusing. A `rerank_score` field on `RetrievedPassage` would be cleaner.

- **Decision**: `rerank_count` is a public attribute on both `FakeReranker` and `ScoreReranker`.
  **Why**: Enables tests and monitoring to verify that the reranker was actually called and how many times, without adding a mock layer.
  **Tradeoff**: `rerank_count` is not part of the `Reranker` protocol, so code typed against the protocol cannot access it.

---

## Scaling concerns

- **Cross-encoder latency**: A real cross-encoder model (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) scores each `(query, passage)` pair independently. For `top_k=20` passages, this is 20 model forward passes (or one batched forward pass of size 20). Cross-encoders are 5–20x slower than bi-encoders at equivalent model size. This latency must be budgeted into end-to-end query response time.
- **Batch sizing**: For GPU cross-encoders, all `(query, passage)` pairs should be batched into a single forward pass. If `top_k` is larger than the GPU's maximum batch size, results must be chunked. `ScoreReranker` calls `scorer` sequentially; a batched variant is needed for GPU-based scorers.
- **`top_n` and truncation**: Truncating the reranked list to `top_n` means the generator sees fewer passages than the vector store returned. If `top_n` is too small, recall suffers. If `top_n` equals `top_k`, the reranker adds latency without reducing generator context size. Typical production configurations use `top_k=20` at retrieval and `top_n=3–5` after reranking.
- **Synchronous blocking**: `rerank` is synchronous. For provider-hosted reranker APIs (Cohere Rerank, Jina), the network call blocks. An async `rerank` variant is needed for production serving.

---

## Future improvements

- **Cross-encoder adapter**: Add a `CrossEncoderReranker` in the `rag` optional extra wrapping `sentence-transformers.CrossEncoder`, which batches all pairs in a single `predict` call.
- **Provider reranker adapters**: Add `CohereReranker` and `JinaReranker` as thin wrappers that call the respective reranking APIs and map their output to the `Reranker` protocol.
- **Async `rerank` method**: Add an `AsyncReranker` protocol variant with `async def rerank(...)` for non-blocking operation in async serving frameworks.
- **`rerank_score` field on `RetrievedPassage`**: Add an optional `rerank_score: float | None = None` field so the reranker's score is preserved alongside the original retrieval score for downstream inspection and logging.
- **Reciprocal Rank Fusion**: Add a `RrfReranker` that combines multiple ranked lists (e.g. dense + sparse) using RRF, useful for hybrid retrieval pipelines.

---

## Usage examples

**FakeReranker in a test:**

```python
from llm_agents.rag.retrieval import RetrievedPassage
from llm_agents.rag.reranking import FakeReranker

passages = [
    RetrievedPassage(doc_id="a", text="first", score=0.9),
    RetrievedPassage(doc_id="b", text="second", score=0.8),
    RetrievedPassage(doc_id="c", text="third", score=0.7),
]
reranker = FakeReranker(top_n=2)
result = reranker.rerank("my query", passages)
# reversed and truncated: ["c", "b"]
assert result[0].doc_id == "c"
assert len(result) == 2
assert reranker.rerank_count == 1
```

**ScoreReranker with a keyword scorer:**

```python
from llm_agents.rag.retrieval import RetrievedPassage
from llm_agents.rag.reranking import ScoreReranker

def keyword_score(query: str, passage: RetrievedPassage) -> float:
    return sum(1 for word in query.lower().split() if word in passage.text.lower())

passages = [
    RetrievedPassage(doc_id="a", text="Python is a programming language"),
    RetrievedPassage(doc_id="b", text="Python and Go are both used for services"),
]
reranker = ScoreReranker(scorer=keyword_score, top_n=1)
result = reranker.rerank("Python language", passages)
assert result[0].doc_id == "a"
```

**Protocol runtime check:**

```python
from llm_agents.rag.reranking import FakeReranker, Reranker, ScoreReranker

assert isinstance(FakeReranker(), Reranker)
assert isinstance(ScoreReranker(scorer=lambda q, p: 0.0), Reranker)
```
