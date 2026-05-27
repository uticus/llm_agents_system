# Module Assignment: Indexing
# Path: src/llm_agents/rag/indexing/
# Layer: rag
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 21

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Turn documents into searchable vectors: chunk -> embed -> upsert into a vector store, with
stable chunk ids for incremental updates.

## Background / problem

Ingestion needs a reusable "make this document searchable" step. Indexing composes chunking,
embeddings, and the vector store into one operation.

## Scope

### In scope
- A chunking step (reuse `core/long_context` chunking) producing stable chunk ids.
- Embed chunks via `rag/embeddings` and upsert into `rag/vector_store` with source metadata.
- Idempotent upsert so re-indexing an unchanged document is a no-op.

### Out of scope
- Document fetching/parsing (owned by `data`).
- Query-time retrieval (owned by `rag/retrieval`).

## Proposed public surface (for Architect to refine)
- `Indexer`, `index_document(doc)`, `index_documents(docs)`.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- pytest; unit tests use a fake embedder + in-memory vector store.
- Public surface re-exported from `rag/indexing/__init__.py`.

## Dependencies
- `core/long_context` (chunking), `rag/embeddings`, `rag/vector_store`, `infra/tracing`.

## Success criteria
- [ ] A document is chunked, embedded, and upserted with stable ids.
- [ ] Re-indexing an unchanged document does not duplicate records.
- [ ] Tests cover chunk id stability and idempotent upsert.

## Open questions
- Chunk id scheme (content hash vs source+offset).
- Chunk size/overlap defaults (shared with long_context).
