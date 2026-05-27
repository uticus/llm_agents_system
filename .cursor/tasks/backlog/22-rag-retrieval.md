# Module Assignment: Retrieval
# Path: src/llm_agents/rag/retrieval/
# Layer: rag
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 22

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Retrieve relevant passages for a query via dense passage retrieval over the vector store,
behind a `Retriever` interface.

## Background / problem

Grounding needs the right passages. Retrieval embeds the query and finds nearest neighbors,
returning candidates (with scores and source metadata) for optional reranking.

## Scope

### In scope
- A `Retriever` interface: query -> ranked candidate passages with scores and metadata.
- Dense retrieval using `rag/embeddings` + `rag/vector_store` (top-k, metadata filters).
- Optional hybrid hook (keyword + dense) left as a seam.

### Out of scope
- Reranking (owned by `rag/reranking`).
- Answer generation (owned by `rag/pipeline`).

## Proposed public surface (for Architect to refine)
- `Retriever` (protocol), `DenseRetriever`, `RetrievedPassage`.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- pytest; unit tests use a fake embedder + in-memory vector store.
- Public surface re-exported from `rag/retrieval/__init__.py`.

## Dependencies
- `rag/embeddings`, `rag/vector_store`, `infra/tracing`.

## Success criteria
- [ ] A query returns top-k passages ordered by similarity, with metadata.
- [ ] Metadata filters constrain results.
- [ ] Tests cover ordering and filtering with fakes.

## Open questions
- Hybrid (BM25 + dense) now or later?
- Default top-k and score thresholds.
