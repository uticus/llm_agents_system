# Module Assignment: Reranking
# Path: src/llm_agents/rag/reranking/
# Layer: rag
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 23

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Reorder retrieved passages by relevance using a cross-encoder, behind a `Reranker` interface,
to improve grounding precision before generation.

## Background / problem

Dense retrieval recalls many candidates but ranks them coarsely. A cross-encoder reranks
query+passage pairs for sharper top-N selection, reducing irrelevant context (and tokens).

## Scope

### In scope
- A `Reranker` interface: (query, passages) -> reordered passages with rerank scores.
- A cross-encoder adapter (behind the `rag` extra).
- Top-N truncation after reranking to fit a context budget.

### Out of scope
- Initial retrieval (owned by `rag/retrieval`).

## Proposed public surface (for Architect to refine)
- `Reranker` (protocol), `CrossEncoderReranker`.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- Cross-encoder model behind the `rag` extra; no heavy imports at module top level.
- pytest; unit tests use a fake reranker (deterministic scores).
- Public surface re-exported from `rag/reranking/__init__.py`.

## Dependencies
- `infra/model_hub` (cross-encoder), `infra/tracing`.

## Success criteria
- [ ] Passages are reordered by rerank score and truncated to top-N.
- [ ] A fake reranker supports tests without a real model.
- [ ] Tests cover reordering and truncation.

## Open questions
- Default cross-encoder model.
- Whether reranking is always on or policy-driven (latency tradeoff).
