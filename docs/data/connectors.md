# data/connectors

## Overview

The connectors module provides the mechanism for pulling raw documents from external data sources into the llm_agents_system platform. Its purpose is to abstract away the specifics of any upstream system — whether a relational database, a wiki, an issue tracker, or a cloud drive — behind a single uniform structural protocol. Callers do not need to know how a source is queried, authenticated, or paginated; they only interact with `Connector.fetch()` and receive a stream of `Document` objects. The module also provides a `FakeConnector` for deterministic testing and a shared `Document` dataclass that travels from this layer into the parsers and then into the ingestion pipeline.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `Document` | dataclass | Single document fetched from an external source, carrying raw content, source metadata, and an opaque cursor. |
| `Connector` | Protocol | Structural interface that any external source connector must satisfy. |
| `FakeConnector` | class | Deterministic test connector that yields preset `Document` objects with cursor-based incremental fetch. |

### `Document`

```python
@dataclass
class Document:
    doc_id:   str
    content:  str
    source:   str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    cursor:   Any = None
```

All fields are positional or keyword. `cursor` is intentionally opaque (`Any`) so that different connector backends can use timestamps, integer offsets, revision IDs, or any other value their source provides.

### `Connector` Protocol

```python
@runtime_checkable
class Connector(Protocol):
    name: str

    async def fetch(self, since_cursor: Any = None) -> AsyncIterator[Document]:
        ...
```

The protocol is `@runtime_checkable`, meaning `isinstance(obj, Connector)` works at runtime. Any class that exposes a `name` attribute and a coroutine `fetch` method satisfies the protocol without subclassing.

### `FakeConnector`

```python
class FakeConnector:
    def __init__(self, name: str, documents: list[Document]) -> None: ...
    async def fetch(self, since_cursor: Any = None) -> AsyncIterator[Document]: ...

    fetch_count: int  # number of times fetch() has been called
```

Cursors are auto-assigned as integer indices (0-based) if `doc.cursor is None` at construction time. When `since_cursor` is an integer, only documents whose cursor is strictly greater are yielded, enabling replay of incremental fetch behaviour in tests.

---

## Architecture

### Conceptual view

```
External Source
  (DB / Wiki / Drive)
         |
         v
   [ Connector ]   <-- implements name: str + fetch(since_cursor) -> AsyncIterator[Document]
         |
         v
    [ Document ]   <-- doc_id, content, source, metadata, cursor
         |
         v
  IngestionPipeline  (data/ingestion)
```

The `Connector` sits at the boundary between the external world and the internal platform. Its only job is to produce `Document` objects. Everything downstream — parsing, chunking, deduplication, embedding — is handled by other modules.

### Data flow

1. The caller (typically `IngestionPipeline`) calls `connector.fetch(since_cursor)`.
2. The connector queries the external source, starting from the position indicated by `since_cursor` (or from the beginning when `None`).
3. For each record in the source, the connector yields one `Document` carrying the raw text content, a stable `doc_id`, the connector's `name` as `source`, any available metadata, and the cursor value for that record.
4. `IngestionPipeline` consumes the `AsyncIterator[Document]` in an `async for` loop, recording the last cursor for the next incremental run.

### Key abstractions

**`Document`** models a single retrievable unit from a source. It deliberately carries `content: str` (not bytes) because connectors are responsible for any encoding conversion at the source boundary. The `cursor` field is kept as `Any` to avoid coupling the protocol to any specific cursor type; the interpretation is entirely connector-defined.

**`Connector` Protocol** is structural (duck-typed) and `@runtime_checkable`. This means third-party connector implementations do not depend on this package at import time; they only need matching attribute shapes. The protocol uses `AsyncIterator` because fetching from a remote source is inherently I/O-bound and may involve pagination.

---

## Design decisions and tradeoffs

- **Decision**: Use a structural `Protocol` rather than an abstract base class.
  **Why**: Allows third-party connector implementations to satisfy the interface without importing from this package, reducing coupling.
  **Tradeoff**: Static type checkers may miss mismatches that a method-resolution-order check would catch; `@runtime_checkable` only checks the presence of methods, not their signatures.

- **Decision**: `fetch` returns `AsyncIterator[Document]` rather than a `list`.
  **Why**: External sources can be very large; streaming avoids loading all documents into memory at once.
  **Tradeoff**: Callers must use `async for`, which requires an async context. Synchronous callers need an event loop wrapper.

- **Decision**: `since_cursor` is typed as `Any`.
  **Why**: Different sources use different cursor types (timestamps, integers, opaque strings). A generic type avoids forcing callers to adapt their cursor to a fixed schema.
  **Tradeoff**: No static enforcement that the cursor type matches what the connector actually produces; a type mismatch only surfaces at runtime.

- **Decision**: `FakeConnector` auto-assigns integer cursors on construction.
  **Why**: Makes incremental fetch testable without requiring the test author to manually set cursor values.
  **Tradeoff**: Documents supplied with explicit non-integer cursors will not support integer-based `since_cursor` filtering.

---

## Scaling concerns

The `Connector` protocol is designed for I/O-bound, streaming access. The `InMemoryVectorStore` and `FakeConnector` used in tests hold everything in process memory and are not suitable for production. Real connector implementations must handle:

- **Pagination**: The protocol provides no built-in pagination; connectors are responsible for iterating pages internally and yielding individual documents.
- **Backpressure**: Python's async generator protocol has no built-in backpressure. If the ingestion pipeline is slower than the connector, all yielded `Document` objects accumulate in the event loop's internal buffers.
- **Connection pooling**: Each `fetch` call should reuse persistent connections. A connector that opens a new connection per document will exhaust connection limits quickly.
- **Cursor durability**: If the process crashes mid-fetch, the cursor from the previous successful run must be persisted externally by the caller; the `Connector` protocol has no built-in cursor persistence.

---

## Future improvements

- **Typed cursor generics**: Parameterise `Connector` with a `CursorT` type variable so static analysis can verify cursor type consistency between producer and consumer.
- **Built-in retry and backoff**: Add a decorator or wrapper that retries failed `fetch` calls with exponential backoff, which every real connector will need.
- **Cursor persistence contract**: Add an optional `save_cursor` / `load_cursor` method pair to the protocol or provide a companion `CursorStore` interface, making durable incremental state a first-class concern.
- **Batch-yield variant**: Add an optional `fetch_batch(since_cursor, batch_size)` method so high-throughput connectors can yield lists of documents rather than one at a time, reducing per-yield overhead.
- **Authentication helpers**: Provide a small credential-management mixin that real connectors (PostgreSQL, Confluence, Google Drive) can share rather than each implementing its own auth logic.

---

## Usage examples

**Basic usage with FakeConnector:**

```python
import asyncio
from llm_agents.data.connectors import Document, FakeConnector

docs = [
    Document(doc_id="a", content="Hello world", source="wiki"),
    Document(doc_id="b", content="Second document", source="wiki"),
]
connector = FakeConnector(name="wiki", documents=docs)

async def run():
    async for doc in connector.fetch():
        print(doc.doc_id, doc.content)

asyncio.run(run())
```

**Incremental fetch with cursor:**

```python
import asyncio
from llm_agents.data.connectors import Document, FakeConnector

docs = [Document(doc_id=str(i), content=f"doc {i}") for i in range(5)]
connector = FakeConnector(name="src", documents=docs)

async def run():
    # First run: fetch all
    last_cursor = None
    async for doc in connector.fetch(since_cursor=None):
        last_cursor = doc.cursor

    # Second run: fetch only new documents
    async for doc in connector.fetch(since_cursor=last_cursor):
        print("new:", doc.doc_id)

asyncio.run(run())
```

**Verifying protocol conformance at runtime:**

```python
from llm_agents.data.connectors import Connector, FakeConnector

connector = FakeConnector(name="test", documents=[])
assert isinstance(connector, Connector)  # True — runtime_checkable
```
