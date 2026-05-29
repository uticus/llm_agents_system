# llm_agents_system — Documentation Index

## What this system is

`llm_agents_system` is a Python platform for building and orchestrating LLM-based agent
systems.  It covers the full lifecycle: model access, data ingestion, retrieval-augmented
generation (RAG), agent capabilities, HTTP serving, fine-tuning, and evaluation.

All modules are implemented in pure Python 3.12+ with optional heavy dependencies kept
behind extras (`openai`, `training`, `serving`).  Every public interface is a structural
`Protocol` — components are interchangeable without inheritance.

---

## System architecture

### Layer diagram

```
+------------------------------------------------------------------+
|  serving layer                                                   |
|  FastAPI application — /health  /chat  /rag/answer               |
+------------------------------------------------------------------+
         |                            |
         v                            v
+------------------+      +--------------------------+
|  core layer      |      |  rag layer               |
|  agent_memory    |      |  pipeline                |
|  long_context    |      |    retrieval             |
|  tool_orchestrat.|      |    reranking             |
|  planning        |      |    embeddings            |
|  hierarchical    |      |    vector_store          |
|  replay_analysis |      |    indexing              |
|  prompting       |      +-----------+--------------+
+------------------+                  |
                                      v
                         +--------------------------+
                         |  data layer              |
                         |  ingestion               |
                         |    connectors            |
                         |    parsers               |
                         +--------------------------+

+------------------------------------------------------------------+
|  infra layer  (cross-cutting — used by every layer above)        |
|  tracing  observability  inference_routing  model_hub            |
|  cost_latency_optimization  guardrails                           |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
|  training layer  (offline — separate from serving path)          |
|  fine_tuning  datasets  experiment_tracking                      |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
|  evaluation layer  (offline + CI)                                |
|  framework  prompts  benchmarking  hallucination                 |
+------------------------------------------------------------------+
```

### End-to-end request flow (RAG serving path)

```
HTTP client
    |
    | POST /rag/answer {query, top_k, filters}
    v
serving/api  (_routes.py — FastAPI handler)
    |
    | 1. guardrail chain — keyword/embedding pre-check
    v
rag/pipeline  (RagPipeline.answer)
    |
    | 2. retrieve top_k passages
    v
rag/retrieval  (DenseRetriever.retrieve)
    |
    | 3. embed query
    v
rag/embeddings  (Embedder.embed)
    |
    | 4. vector search
    v
rag/vector_store  (InMemoryVectorStore.search)
    |
    | 5. optional rerank
    v
rag/reranking  (Reranker.rerank)
    |
    | 6. generate grounded answer
    v
core/prompting  (PromptTemplate.format)
    |
    v
infra/inference_routing  (Router.complete — retry + fallback)
    |
    v
infra/model_hub  (Backend.generate)
    |
    | 7. cost + latency tracking
    v
infra/cost_latency_optimization  (BudgetTracker, CompletionCache)
    |
    | 8. tracing + metrics export
    v
infra/tracing + infra/observability
    |
    v
GroundedAnswer  {answer, passages}  --HTTP--> client
```

### Offline ingestion and indexing flow

```
external source
    |
data/connectors  (Connector.fetch_since)
    |  Document(doc_id, content, source, metadata)
    v
data/parsers  (DocumentParser.parse)
    |  ParsedDocument(doc_id, text, metadata)
    v
data/ingestion  (IngestionPipeline.ingest)
    |  MD5 dedup at document level
    |  TextChunker.chunk -> list[str]
    v
rag/indexing  (Indexer.index)
    |  MD5 dedup at chunk level
    |  batch embed -> upsert with chunk_id = "doc_id#N"
    v
rag/vector_store  (VectorStore.upsert)
```

### Training / fine-tuning flow

```
datasets  (DatasetLoader.from_jsonl / from_prodigy)
    |  Dataset.split(train_ratio) -> (train, val)
    v
training/fine_tuning  (FineTuner.run)
    |  trainer_factory -> train -> save -> get_metrics
    v
training/experiment_tracking  (Tracker.log_metrics / log_params)
    |  NoOpTracker (prod) or InMemoryTracker (tests)
    v
FineTuneResult(model_path, metrics, run_id, artifact_uri)
```

---

## Module documentation

### infra — infrastructure (cross-cutting)

| Module | Description | Doc |
|---|---|---|
| tracing | Span lifecycle, async-safe context propagation, `InMemoryCollector` | [infra/tracing.md](infra/tracing.md) |
| observability | Prometheus metrics, JSON structured logging, span bridge | [infra/observability.md](infra/observability.md) |
| inference_routing | Multi-backend retry + fallback, `RoutingPolicy`, span instrumentation | [infra/inference_routing.md](infra/inference_routing.md) |
| cost_latency_optimization | LRU completion cache, async request batcher, budget tracker | [infra/cost_latency_optimization.md](infra/cost_latency_optimization.md) |
| model_hub | Backend registry, OpenAI + HuggingFace + GGUF adapters | [infra/model_hub.md](infra/model_hub.md) |
| guardrails | Keyword / embedding / LLM filter chain, `GuardrailResult` | [infra/guardrails.md](infra/guardrails.md) |

### core — agent capabilities

| Module | Description | Doc |
|---|---|---|
| agent_memory | Short-term + long-term `Memory` store, `MemoryEntry`, scorer-based recall | [core/agent_memory.md](core/agent_memory.md) |
| long_context | Window strategies (sliding, summary, topic), `ContextManager` Protocol | [core/long_context.md](core/long_context.md) |
| tool_orchestration | `Tool` Protocol, `ToolRegistry`, `ToolOrchestrator` (sequential / parallel) | [core/tool_orchestration.md](core/tool_orchestration.md) |
| planning | `Plan` / `Step`, `Planner` Protocol, `SimplePlanner`, `ReactivePlanner` | [core/planning.md](core/planning.md) |
| hierarchical_agents | `AgentNode` Protocol, `Coordinator`, `WorkerAgent`, multi-level delegation | [core/hierarchical_agents.md](core/hierarchical_agents.md) |
| replay_analysis | `Event` log, `ReplaySession`, `ReplayAnalyzer` (pattern detection) | [core/replay_analysis.md](core/replay_analysis.md) |
| prompting | `PromptTemplate`, `FewShotTemplate`, `ExampleSelector` | [core/prompting.md](core/prompting.md) |

### data — ingestion pipeline

| Module | Description | Doc |
|---|---|---|
| connectors | `Document`, `Connector` Protocol, `FakeConnector` (cursor-based incremental fetch) | [data/connectors.md](data/connectors.md) |
| parsers | `ParsedDocument`, `DocumentParser` Protocol, `TextParser`, `ParserRegistry` | [data/parsers.md](data/parsers.md) |
| ingestion | `IngestionPipeline` (fetch → dedup → parse → chunk → upsert), `IngestionReport` | [data/ingestion.md](data/ingestion.md) |

### rag — retrieval-augmented generation

| Module | Description | Doc |
|---|---|---|
| embeddings | `Embedder` Protocol, `FakeEmbedder`, `BatchEmbedder` | [rag/embeddings.md](rag/embeddings.md) |
| vector_store | `VectorStore` Protocol, `InMemoryVectorStore` (cosine similarity), `SearchResult` | [rag/vector_store.md](rag/vector_store.md) |
| indexing | `Indexer` (chunk → MD5 dedup → batch embed → upsert), `IndexReport` | [rag/indexing.md](rag/indexing.md) |
| retrieval | `DenseRetriever` (embed → search → filter), `RetrievedPassage` | [rag/retrieval.md](rag/retrieval.md) |
| reranking | `Reranker` Protocol, `FakeReranker`, `ScoreReranker` | [rag/reranking.md](rag/reranking.md) |
| pipeline | `RagPipeline` (retrieve → rerank → generate), `GroundedAnswer` | [rag/pipeline.md](rag/pipeline.md) |

### evaluation — offline quality assessment

| Module | Description | Doc |
|---|---|---|
| framework | `EvalCase`, `Metric` Protocol, `EvalHarness`, `EvalReport`, `aggregate` | [evaluation/framework.md](evaluation/framework.md) |
| prompts | `PromptVariant`, `VariantResult`, `PromptComparison`, `compare` | [evaluation/prompts.md](evaluation/prompts.md) |
| benchmarking | `BenchmarkTask`, `Suite`, `BenchmarkRunner`, p95 latency, CLI entrypoint | [evaluation/benchmarking.md](evaluation/benchmarking.md) |
| hallucination | `HallucinationDetector` Protocol, `OverlapDetector`, `LLMJudgeDetector`, `HallucinationReport` | [evaluation/hallucination.md](evaluation/hallucination.md) |

### training — model improvement

| Module | Description | Doc |
|---|---|---|
| fine_tuning | `FineTuner`, `FineTuneConfig`, `FineTuneResult`, trainer_factory injection | [training/fine_tuning.md](training/fine_tuning.md) |
| datasets | `Dataset` (split, validate, version hash), `DatasetLoader`, `from_prodigy` | [training/datasets.md](training/datasets.md) |
| experiment_tracking | `Tracker` Protocol, `NoOpTracker`, `InMemoryTracker` | [training/experiment_tracking.md](training/experiment_tracking.md) |

### serving — HTTP API

| Module | Description | Doc |
|---|---|---|
| api | FastAPI app, `/health` `/chat` `/rag/answer`, Pydantic schemas | [serving/api.md](serving/api.md) |

---

## Cross-cutting design principles

**Structural protocols over inheritance.**
Every public interface is a `@runtime_checkable Protocol`.  Any object with the right
methods satisfies it — no base class required.  `isinstance()` checks work at runtime.

**Light-core principle.**
The default install has no heavy third-party dependencies.  Optional extras (`openai`,
`training`, `serving`) gate the heavy imports.  All optional imports are deferred to
the first call site inside the relevant function so that importing a module without
its extra does not fail.

**Deterministic test doubles.**
Every module ships a `FakeXxx` implementation (or `InMemoryXxx` / `NoOpXxx`) that is
fully deterministic, requires no network or disk access, and is usable as a drop-in
in unit tests.

**Content-hash deduplication.**
MD5 hashes are used at two levels in the ingestion/indexing path:
- Document level in `IngestionPipeline` — skips re-parsing unchanged documents.
- Chunk level in `Indexer` — skips re-embedding unchanged chunks.
Both levels use in-process `set[str]`; durability across restarts requires an external
store (documented as a scaling concern in each module's doc).

**Async-safe tracing.**
`contextvars.ContextVar` (not thread-local storage) propagates the active span across
`await` boundaries.  Span lifecycle is split into `Span` (open) and `FinishedSpan`
(immutable) to enforce correct usage at the type level.

---

## Quick start

```python
# Minimal RAG pipeline — no external dependencies
from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.vector_store import InMemoryVectorStore
from llm_agents.rag.indexing import Indexer
from llm_agents.rag.retrieval import DenseRetriever
from llm_agents.rag.pipeline import RagPipeline

embedder = FakeEmbedder(dimensions=8)
store = InMemoryVectorStore()
indexer = Indexer(embedder=embedder, store=store)

indexer.index("doc1", "Paris is the capital of France.", metadata={"text": "Paris is the capital of France."})
indexer.index("doc2", "The Eiffel Tower is in Paris.", metadata={"text": "The Eiffel Tower is in Paris."})

retriever = DenseRetriever(embedder=embedder, store=store, top_k=2)

def generator(query, passages):
    context = " ".join(p.text for p in passages if p.text)
    return f"Based on: {context}"

pipeline = RagPipeline(retriever=retriever, generator=generator)
result = pipeline.answer("What is the capital of France?")
print(result.answer)
print(result.passages)
```

```python
# Hallucination detection
from llm_agents.evaluation.hallucination import OverlapDetector

detector = OverlapDetector(threshold=0.5)
report = detector.detect(
    answer="Paris is the capital of France.",
    references=["Paris is the capital of France and home to the Eiffel Tower."],
)
print(report.groundedness_score)   # ~0.8
print(report.is_hallucination)     # False
```

```python
# Experiment tracking
from llm_agents.training.experiment_tracking import InMemoryTracker

tracker = InMemoryTracker()
run_id = tracker.start_run("experiment-1", config={"lr": 1e-4, "epochs": 3})
tracker.log_metrics({"loss": 0.42, "acc": 0.91}, run_id=run_id, step=1)
tracker.end_run(run_id)
print(tracker.metrics)
```

---

## File layout

```
src/llm_agents/
  infra/
    tracing/             Span, SpanContext, InMemoryCollector
    observability/       MetricsRegistry, JSONFormatter, bridge_span
    inference_routing/   Router, RoutingPolicy, Candidate
    cost_latency_optimization/  CompletionCache, Batcher, BudgetTracker
    model_hub/           ModelHub, OpenAIBackend, HuggingFaceBackend
    guardrails/          GuardrailChain, KeywordFilter, EmbeddingFilter
  core/
    agent_memory/        Memory, MemoryEntry, ShortTermMemory, LongTermMemory
    long_context/        ContextManager, SlidingWindowStrategy, SummaryStrategy
    tool_orchestration/  Tool, ToolRegistry, ToolOrchestrator
    planning/            Plan, Step, SimplePlanner, ReactivePlanner
    hierarchical_agents/ AgentNode, Coordinator, WorkerAgent
    replay_analysis/     Event, ReplaySession, ReplayAnalyzer
    prompting/           PromptTemplate, FewShotTemplate, ExampleSelector
  data/
    connectors/          Document, Connector, FakeConnector
    parsers/             ParsedDocument, DocumentParser, TextParser, ParserRegistry
    ingestion/           IngestionPipeline, IngestionReport
  rag/
    embeddings/          Embedder, FakeEmbedder, BatchEmbedder
    vector_store/        VectorStore, InMemoryVectorStore, SearchResult
    indexing/            Indexer, IndexReport
    retrieval/           DenseRetriever, RetrievedPassage
    reranking/           Reranker, FakeReranker, ScoreReranker
    pipeline/            RagPipeline, GroundedAnswer
  evaluation/
    framework/           EvalCase, EvalResult, EvalReport, EvalHarness, Metric
    prompts/             PromptVariant, VariantResult, PromptComparison, compare
    benchmarking/        BenchmarkTask, Suite, BenchmarkRunner, BenchmarkReport
    hallucination/       HallucinationReport, HallucinationDetector, OverlapDetector, LLMJudgeDetector
  training/
    fine_tuning/         FineTuner, FineTuneConfig, FineTuneResult
    datasets/            Dataset, Example, DatasetLoader, from_prodigy
    experiment_tracking/ Tracker, NoOpTracker, InMemoryTracker
  serving/
    api/                 create_app, build_router, ChatRequest, RagRequest, HealthResponse

tests/unit/              mirrors src/ — one test file per module
docs/                    this directory
  index.md               this file
  infra/                 6 module docs
  core/                  7 module docs
  data/                  3 module docs
  rag/                   6 module docs
  evaluation/            4 module docs
  training/              3 module docs
  serving/               1 module doc
```
