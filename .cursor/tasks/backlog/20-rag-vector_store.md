# Module Assignment: Vector store
# Path: src/llm_agents/rag/vector_store/
# Layer: rag
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 20

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Store and query vectors behind a `VectorStore` interface, with adapters for FAISS (local)
and a server option (pgvector / Weaviate / Chroma / Elasticsearch).

## Background / problem

Retrieval needs a similarity index. One interface lets the platform start local (FAISS) and
scale to a server-backed store without touching callers.

## Scope

### In scope
- A `VectorStore` interface: upsert (id, vector, payload), similarity search (top-k),
  delete, filter by metadata.
- A FAISS in-memory/local adapter (behind the `rag` extra).
- At least one server adapter seam (recommend pgvector, since PostgreSQL is already used).

### Out of scope
- Embedding (owned by `rag/embeddings`).
- Chunking (owned by `rag/indexing`).

## Proposed public surface (for Architect to refine)
- `VectorStore` (protocol), `Record`, `FaissStore`, a server-store adapter.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- Backends behind the `rag`/`data` extras; no heavy imports at module top level.
- pytest; unit tests use an in-memory fake store.
- Public surface re-exported from `rag/vector_store/__init__.py`.

## Dependencies
- `infra/tracing`.

## Success criteria
- [ ] Upsert + top-k similarity search + metadata filter work behind the interface.
- [ ] A FAISS adapter and an in-memory fake both pass the same contract tests.
- [ ] Tests cover upsert, search ordering, and filtering.

## Open questions
- Which server store to implement first (pgvector recommended).
- Similarity metric convention (must match embeddings normalization).
