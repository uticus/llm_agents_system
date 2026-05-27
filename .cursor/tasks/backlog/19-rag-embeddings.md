# Module Assignment: Embeddings
# Path: src/llm_agents/rag/embeddings/
# Layer: rag
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 19

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Produce text embeddings behind an `Embedder` interface, with adapters for
sentence-transformers (local) and provider embeddings (e.g. OpenAI).

## Background / problem

Retrieval and semantic memory need vector representations. A single interface lets indexing,
retrieval, and memory swap embedding backends without code changes.

## Scope

### In scope
- An `Embedder` interface (embed texts -> vectors; expose dimension/model id).
- A sentence-transformers adapter (behind the `rag` extra) and a provider-embeddings adapter
  (via `infra/model_hub`).
- Batch embedding.

### Out of scope
- Vector storage (owned by `rag/vector_store`).

## Proposed public surface (for Architect to refine)
- `Embedder` (protocol), `SentenceTransformerEmbedder`, `ProviderEmbedder`.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- Local models behind the `rag` extra; no heavy imports at module top level.
- pytest; unit tests use a fake embedder (deterministic vectors), never real models.
- Public surface re-exported from `rag/embeddings/__init__.py`.

## Dependencies
- `infra/model_hub` (provider embeddings), `infra/tracing`.

## Success criteria
- [ ] Texts embed to fixed-dimension vectors behind the interface.
- [ ] Both a local and a provider adapter exist; a fake embedder supports tests.
- [ ] Tests cover batching and dimension consistency.

## Open questions
- Default embedding model and dimension.
- Normalization (cosine vs dot) convention shared with vector_store.
