# data/ingestion

## Overview

The ingestion module orchestrates the complete document intake pipeline: it fetches raw documents from a connector, parses them, applies caller-supplied chunking, deduplicates on content hash, and calls an upsert callback for each new chunk. This module is the glue layer between the data acquisition tier (connectors, parsers) and the RAG indexing tier (`rag/indexing`). A single `IngestionPipeline` instance can be called repeatedly for incremental runs; it remembers which content hashes it has already processed so that unchanged documents are skipped without re-embedding or re-indexing. Run statistics are returned in an `IngestionReport` for observability.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `IngestionPipeline` | class | Orchestrates fetch -> parse -> chunk -> dedup -> upsert. |
| `IngestionReport` | dataclass | Per-run statistics: fetched, parsed, skipped, upserted, errors. |

### `IngestionReport`

```python
@dataclass
class IngestionReport:
    fetched:  int = 0
    parsed:   int = 0
    skipped:  int = 0
    upserted: int = 0
    errors:   list[str] = field(default_factory=list)
```

Each field counts events for a single `ingest()` call. `errors` holds human-readable strings of the form `"<doc_id>: parse error — <exception>"`.

### `IngestionPipeline`

```python
class IngestionPipeline:
    def __init__(
        self,
        connector: Any,   # satisfies Connector protocol
        parser:    Any,   # satisfies DocumentParser protocol
        chunker:   Callable[[ParsedDocument], list[Any]],
        upsert:    Callable[[Any], None],
    ) -> None: ...

    async def ingest(self, since_cursor: Any = None) -> IngestionReport: ...

    @property
    def seen_count(self) -> int: ...   # unique content hashes accumulated
    def reset_dedup(self) -> None: ... # clear hash set for a fresh run
```

`connector`, `parser`, `chunker`, and `upsert` are stored by reference and not validated at construction time; mismatches surface on the first `ingest` call.

Key internal attribute: `_seen_hashes: set[str]` — persists across `ingest` calls on the same instance.

---

## Architecture

### Conceptual view

```
Connector.fetch(since_cursor)
         |
         v AsyncIterator[Document]
  +--------------+
  |  for each    |
  |  Document    |
  |              |
  |  MD5(content)|-----> _seen_hashes ---> skip (report.skipped += 1)
  |              |
  |  parser.parse|-----> ParsedDocument
  |              |
  |  chunker(pd) |-----> list[chunk]
  |              |
  |  for chunk   |
  |  upsert(chunk)|---> downstream (e.g. Indexer.index)
  +--------------+
         |
         v
   IngestionReport
```

### Data flow

1. `ingest(since_cursor)` opens an async iteration over `connector.fetch(since_cursor)`.
2. For each `Document`:
   a. Compute `MD5(doc.content)`. If the hash is in `_seen_hashes`, increment `report.skipped` and continue to the next document.
   b. Call `parser.parse(doc.content, metadata=doc.metadata, doc_id=doc.doc_id)`. If the parser raises, append to `report.errors` and continue.
   c. Increment `report.parsed` and add the hash to `_seen_hashes`.
   d. Call `chunker(parsed)` to get a list of chunk objects.
   e. For each chunk, call `upsert(chunk)` and increment `report.upserted`.
3. Return the completed `IngestionReport`.

### Key abstractions

**`IngestionPipeline`** is intentionally narrow: it does not know how to embed, how to store vectors, or how to communicate with any specific backend. The `chunker` and `upsert` callables are injected by the caller, which means the pipeline can feed any downstream system — a vector store, a search index, a message queue — by swapping the `upsert` function.

**`IngestionReport`** provides a structured summary rather than log lines, so callers can make programmatic decisions (e.g. alert when `len(report.errors) > 0`, or report metrics when `report.skipped / report.fetched > 0.9`).

**MD5 deduplication** operates on the full raw `Document.content` string before parsing. This is a content-level check: if the source delivers the same bytes under a different `doc_id`, dedup still fires. This is intentional — the goal is to avoid re-embedding identical text, not to enforce `doc_id` uniqueness.

---

## Design decisions and tradeoffs

- **Decision**: Deduplication is MD5 over raw content, stored in a process-local `set[str]`.
  **Why**: MD5 is fast and adequate for non-security hashing. A process-local set avoids external state (Redis, database) during development and testing.
  **Tradeoff**: The hash set is lost on process restart. For truly durable incremental ingestion, the set must be persisted externally between runs (not currently implemented).

- **Decision**: Parse errors are accumulated in `report.errors` rather than raising.
  **Why**: A single malformed document should not abort an entire ingestion run that may process thousands of documents.
  **Tradeoff**: Silent error accumulation means a caller that does not inspect `report.errors` will miss parse failures entirely.

- **Decision**: The `chunker` is a plain synchronous callable, not a protocol.
  **Why**: Chunking is typically CPU-bound string splitting; a callable is the simplest possible abstraction and avoids forcing callers to create a class.
  **Tradeoff**: No type-level contract on what a chunk looks like; the `upsert` callable must agree with the `chunker` output type through informal convention.

- **Decision**: `upsert` is a plain synchronous callable.
  **Why**: Keeps the pipeline easy to compose; the caller can make `upsert` delegate to `Indexer.index` or any other sink.
  **Tradeoff**: If the upsert operation is I/O-bound (network call to a remote vector DB), it blocks the event loop. An async `upsert` callable would be needed for high-throughput scenarios.

- **Decision**: `_seen_hashes` persists across multiple `ingest` calls on the same instance.
  **Why**: Enables true incremental ingestion — documents seen in earlier runs of the same process session are not re-processed.
  **Tradeoff**: The set grows unbounded over the lifetime of the instance. For very long-running processes ingesting millions of documents, memory growth must be managed by calling `reset_dedup()` or rotating the instance.

---

## Scaling concerns

- **Memory**: `_seen_hashes` stores 32-character hex MD5 strings (~32 bytes each). One million unique documents cost approximately 32 MB. At tens of millions, this becomes significant.
- **Throughput bottleneck**: The `upsert` callable is synchronous. If it performs a remote network call (e.g. to a vector database), the async event loop is blocked per chunk. Wrapping the upsert in `asyncio.get_event_loop().run_in_executor` is the mitigation.
- **Connector speed vs. parser speed**: The pipeline processes documents one at a time. If parsing is slow (e.g. PDF extraction) and the connector is fast, documents pile up. A bounded queue with a worker pool would be needed for parallelism.
- **Error rate monitoring**: There is no built-in alerting if the error rate exceeds a threshold. Production use requires external monitoring of `IngestionReport.errors`.

---

## Future improvements

- **Durable cursor and hash persistence**: Persist `_seen_hashes` and the last `since_cursor` to a database or file between process restarts, making truly resumable ingestion possible.
- **Async upsert support**: Accept `Callable[[Any], Awaitable[None]]` in addition to synchronous callables, so high-throughput upserts can be awaited without blocking the loop.
- **Parallel document processing**: Process multiple documents concurrently using `asyncio.gather` with a configurable concurrency limit (semaphore), improving throughput when parsing is the bottleneck.
- **Metrics integration**: Expose `IngestionReport` fields as counter/gauge metrics (Prometheus, StatsD) so operations teams can monitor pipeline health without parsing log output.
- **Chunk-level dedup**: Optionally deduplicate at the chunk level (not just document level) to avoid re-upserting unchanged chunks when a document is partially updated.

---

## Usage examples

**Minimal pipeline wiring:**

```python
import asyncio
from llm_agents.data.connectors import Document, FakeConnector
from llm_agents.data.parsers import TextParser
from llm_agents.data.ingestion import IngestionPipeline

docs = [
    Document(doc_id="1", content="First document text"),
    Document(doc_id="2", content="Second document text"),
]
connector = FakeConnector(name="test", documents=docs)
parser = TextParser()

collected_chunks: list[str] = []

pipeline = IngestionPipeline(
    connector=connector,
    parser=parser,
    chunker=lambda pd: [pd.text],          # identity chunker
    upsert=lambda chunk: collected_chunks.append(chunk),
)

report = asyncio.run(pipeline.ingest())
print(report.fetched, report.parsed, report.upserted)  # 2 2 2
```

**Incremental ingestion with cursor:**

```python
import asyncio
from llm_agents.data.connectors import Document, FakeConnector
from llm_agents.data.parsers import TextParser
from llm_agents.data.ingestion import IngestionPipeline

docs = [Document(doc_id=str(i), content=f"doc {i}") for i in range(10)]
connector = FakeConnector(name="src", documents=docs)
parser = TextParser()
results: list[str] = []

pipeline = IngestionPipeline(
    connector=connector,
    parser=parser,
    chunker=lambda pd: [pd.text],
    upsert=results.append,
)

# First run — fetch all
report1 = asyncio.run(pipeline.ingest(since_cursor=None))
# Second run — nothing new (all hashes already seen)
report2 = asyncio.run(pipeline.ingest(since_cursor=None))
print(report2.skipped)  # 10 — all documents deduplicated
```

**Inspecting errors:**

```python
import asyncio
from llm_agents.data.connectors import Document, FakeConnector
from llm_agents.data.parsers import TextParser
from llm_agents.data.ingestion import IngestionPipeline

class BrokenParser:
    def parse(self, content, metadata=None, *, doc_id=""):
        raise ValueError("cannot parse")

docs = [Document(doc_id="bad", content="anything")]
connector = FakeConnector(name="src", documents=docs)
pipeline = IngestionPipeline(
    connector=connector,
    parser=BrokenParser(),
    chunker=lambda pd: [pd.text],
    upsert=lambda c: None,
)
report = asyncio.run(pipeline.ingest())
print(report.errors)  # ["bad: parse error — cannot parse"]
```
