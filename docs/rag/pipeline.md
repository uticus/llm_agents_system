# rag/pipeline

## Overview

The RAG pipeline module is the top-level orchestrator for retrieval-augmented generation. It composes a retriever, an optional reranker, and a generator callable into a single `answer(query)` entry point, returning a `GroundedAnswer` that carries the generated text alongside the passages used to produce it. This module is the last stage in the RAG data flow — it sits above `rag/retrieval` and `rag/reranking` and provides the interface that serving or agent components call to answer user questions with source-grounded responses. It has no knowledge of how vectors are stored, how documents were indexed, or what model is generating the text; it only wires together the configured components and passes data between them.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `GroundedAnswer` | dataclass | Result of a pipeline run: query, generated answer, and cited passages. |
| `RagPipeline` | class | Retrieve -> (optionally rerank) -> generate orchestrator. |

### `GroundedAnswer`

```python
@dataclass
class GroundedAnswer:
    query:     str
    answer:    str
    citations: list[RetrievedPassage] = field(default_factory=list)
```

`citations` contains the passages as they were passed to the generator — after retrieval and optional reranking, in the order presented to the generator. This list is the provenance record for the generated answer and enables downstream citation display, factual verification, and logging.

### `RagPipeline`

```python
class RagPipeline:
    def __init__(
        self,
        retriever:  Any,              # has retrieve(query, top_k, filters) -> list[RetrievedPassage]
        generator:  Any,              # Callable[[str, list[RetrievedPassage]], str]
        *,
        reranker:   Any = None,       # optional; has rerank(query, passages, top_n) -> list[RetrievedPassage]
        top_k:      int = 5,
        top_n:      int | None = None,
    ) -> None: ...

    def answer(
        self,
        query:   str,
        *,
        top_k:   int | None = None,
        top_n:   int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> GroundedAnswer: ...

    top_k: int
    top_n: int | None
```

`reranker`, `top_k`, and `top_n` are keyword-only at construction. The `answer` method's `top_k` and `top_n` override the constructor defaults for that call only. `filters` is forwarded directly to the retriever's `retrieve` method.

---

## Architecture

### Conceptual view

```
User query
    |
    v
RagPipeline.answer(query, top_k, top_n, filters)
    |
    |-- retriever.retrieve(query, top_k=k, filters=filters)
    |       |
    |       | (Embedder + VectorStore inside)
    |       v
    |   list[RetrievedPassage]  (cosine-ranked)
    |
    |-- [optional] reranker.rerank(query, passages, top_n=n)
    |       |
    |       v
    |   list[RetrievedPassage]  (reranked, truncated to top_n)
    |
    |-- generator(query, passages)
    |       |
    |       v
    |   answer: str
    |
    v
GroundedAnswer(query, answer, citations=passages)
```

### Data flow

1. `answer(query)` resolves effective `k` (per-call `top_k` or constructor default) and `n` (per-call `top_n` or constructor default).
2. `retriever.retrieve(query, top_k=k, filters=filters)` is called. The retriever embeds the query and searches the vector store, returning at most `k` passages sorted by descending cosine similarity.
3. If `self._reranker is not None`, `reranker.rerank(query, passages, top_n=n)` is called. The passages are re-sorted by a cross-encoder or scorer and optionally truncated to `n`.
4. `generator(query, passages)` is called with the final ranked list. The generator produces a text answer grounded on the passage content.
5. A `GroundedAnswer` is returned with `citations` set to the passages as they were passed to the generator.

### Key abstractions

**`GroundedAnswer`** exists to bundle the answer and its evidence together. Serving code that returns only `answer: str` loses provenance. With `GroundedAnswer`, the caller can display citations in a UI, log the evidence for audit, or run automatic faithfulness checks.

**`RagPipeline`** is intentionally thin. It delegates all intelligence to the retriever, reranker, and generator. The pipeline itself contains no ML logic; it is a sequencing and data-passing layer. This makes it easy to swap any component (e.g. replace `DenseRetriever` with a hybrid dense+sparse retriever) without touching the pipeline code.

**`generator` as a callable** rather than a protocol keeps the interface minimal. Any function `(query: str, passages: list[RetrievedPassage]) -> str` works, whether it calls an LLM API, renders a template, or concatenates passage texts. This means the pipeline can be tested with a trivial lambda generator without mocking a full LLM.

---

## Design decisions and tradeoffs

- **Decision**: `generator` is a plain callable, not a protocol class.
  **Why**: Callable is the simplest interface; any function or class with `__call__` qualifies. This avoids forcing callers to wrap their LLM client in a class that inherits from a `Generator` abstract base.
  **Tradeoff**: No static contract on what arguments the generator receives or what it returns. A generator that ignores `passages` and hallucinates is indistinguishable from one that faithfully grounds its answer.

- **Decision**: `citations` in `GroundedAnswer` are the passages as presented to the generator, not all retrieved passages.
  **Why**: What matters for provenance is what the generator actually saw. If the reranker dropped 15 of 20 passages before the generator call, the 15 dropped passages are not relevant to the answer's provenance.
  **Tradeoff**: Callers who want to inspect all retrieved passages (before reranking) must call `retriever.retrieve` separately.

- **Decision**: `top_n` is `None` by default, not equal to `top_k`.
  **Why**: When `top_n=None`, the reranker receives all `top_k` passages and applies its own truncation (if `reranker.top_n` is set). Setting `top_n=top_k` in the pipeline would override the reranker's own configuration.
  **Tradeoff**: If neither the pipeline nor the reranker has a `top_n` set, the generator receives all `top_k` passages, which may be more context than the LLM's context window can accommodate.

- **Decision**: `filters` are forwarded to the retriever but not to the reranker.
  **Why**: Metadata filters are a retrieval-time constraint (restrict the search space). Reranking operates on the already-filtered result set; there is no meaningful use case for filtering again at the reranking stage.
  **Tradeoff**: If the retriever does not support a `filters` argument, the pipeline will fail at runtime, not at construction time. Type-level validation is absent.

- **Decision**: The pipeline is synchronous.
  **Why**: All sub-components (`retrieve`, `rerank`, `generator`) are currently synchronous; an async pipeline would provide no benefit until at least one of them is async.
  **Tradeoff**: When any component (especially the generator, which calls an LLM API) is made async, the entire pipeline must be refactored to use `async def answer`.

---

## Scaling concerns

- **End-to-end latency**: The pipeline executes `retrieve` + (optional) `rerank` + `generate` sequentially. For an LLM generator calling an external API, `generate` dominates latency (hundreds to thousands of milliseconds). Retrieval and reranking typically add 10–200 ms depending on backend.
- **Concurrency**: `RagPipeline` is stateless after construction (all state is in `retriever`, `reranker`, and `generator`). Multiple threads or coroutines can call `answer` concurrently on the same instance, provided the underlying components are thread-safe or the calls are properly isolated. `InMemoryVectorStore` is not thread-safe; a thread-safe backend is needed for concurrent serving.
- **Context window size**: The `generator` receives `passages` as a list. If `top_k` is large and each passage contains long text, the prompt may exceed the LLM's context window. The `top_n` parameter (set at pipeline or per-call level) is the primary control for this.
- **No streaming**: The current `answer` method blocks until `generator` returns a complete string. Streaming generation (token-by-token) requires a different interface and is not currently supported.

---

## Future improvements

- **Async `answer` method**: Add `async def answer_async(...)` so the generator can be an async function (e.g. `await openai.ChatCompletion.create(...)`) without blocking the event loop.
- **Streaming support**: Add an `answer_stream(query) -> AsyncIterator[str]` variant that yields generated tokens as they arrive from a streaming LLM API, enabling low-latency streaming UI responses.
- **Faithfulness evaluation hook**: Add an optional `evaluator` callable invoked after generation that scores the answer against the citations (e.g. using an NLI model), populating a `faithfulness_score` field on `GroundedAnswer`.
- **Prompt template injection**: Accept an optional `prompt_builder: Callable[[str, list[RetrievedPassage]], str]` that formats the prompt passed to the generator, allowing callers to control context formatting without subclassing the pipeline.
- **Observability hooks**: Add `on_retrieve` and `on_generate` callback arguments called with the intermediate results, enabling tracing, logging, and metric collection without modifying the pipeline internals.

---

## Usage examples

**Minimal pipeline without reranker:**

```python
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.indexing import Indexer
from llm_agents.rag.retrieval import DenseRetriever
from llm_agents.rag.pipeline import RagPipeline

embedder = FakeEmbedder(dimensions=4)
store = InMemoryVectorStore()
indexer = Indexer(embedder=embedder, vector_store=store)
indexer.index("doc-1", "The Eiffel Tower is in Paris.", metadata={"text": "The Eiffel Tower is in Paris."})

retriever = DenseRetriever(embedder=embedder, vector_store=store, top_k=3)

def simple_generator(query: str, passages):
    context = " ".join(p.text for p in passages)
    return f"Based on context: {context}"

pipeline = RagPipeline(retriever=retriever, generator=simple_generator)
result = pipeline.answer("Where is the Eiffel Tower?")
print(result.answer)
print(len(result.citations))
```

**Pipeline with reranker and top_n:**

```python
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.retrieval import DenseRetriever
from llm_agents.rag.reranking import FakeReranker
from llm_agents.rag.pipeline import RagPipeline

embedder = FakeEmbedder(dimensions=4)
store = InMemoryVectorStore()
for i in range(10):
    store.upsert(f"doc-{i}#0", [1.0, 0.0, 0.0, 0.0], metadata={"text": f"passage {i}"})

retriever = DenseRetriever(embedder=embedder, vector_store=store, top_k=10)
reranker = FakeReranker(top_n=3)

pipeline = RagPipeline(
    retriever=retriever,
    generator=lambda q, ps: f"answer based on {len(ps)} passages",
    reranker=reranker,
    top_k=10,
    top_n=3,
)
result = pipeline.answer("query")
assert len(result.citations) == 3
```

**Per-call parameter override with metadata filter:**

```python
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.retrieval import DenseRetriever
from llm_agents.rag.pipeline import RagPipeline

embedder = FakeEmbedder(dimensions=4)
store = InMemoryVectorStore()
store.upsert("a#0", [1.0, 0.0, 0.0, 0.0], metadata={"text": "wiki content", "source": "wiki"})
store.upsert("b#0", [1.0, 0.0, 0.0, 0.0], metadata={"text": "blog content", "source": "blog"})

retriever = DenseRetriever(embedder=embedder, vector_store=store)
pipeline = RagPipeline(retriever=retriever, generator=lambda q, ps: "ok")

result = pipeline.answer(
    "my question",
    top_k=5,
    filters={"source": "wiki"},
)
assert all(p.metadata["source"] == "wiki" for p in result.citations)
```
