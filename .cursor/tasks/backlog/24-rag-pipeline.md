# Module Assignment: RAG pipeline
# Path: src/llm_agents/rag/pipeline/
# Layer: rag
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 24

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Compose retrieval, optional reranking, prompt assembly, and generation into a single
`answer(query)` pipeline that produces grounded responses with citations.

## Background / problem

The end-to-end RAG flow ties together several subsystems. A single pipeline gives callers
one entry point and a consistent place to enforce grounding and guardrails.

## Scope

### In scope
- A pipeline: retrieve -> (rerank) -> build grounded prompt (via `core/prompting`) ->
  generate (via `infra/inference_routing`) -> apply `infra/guardrails`.
- Citations/source attribution in the response.
- Graceful handling of empty/low-relevance retrieval (do not fabricate).

### Out of scope
- The individual retrieval/rerank/generation internals.

## Proposed public surface (for Architect to refine)
- `RagPipeline`, `answer(query) -> GroundedAnswer` (text + citations).

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- LLM calls go through the mockable provider boundary; assert on structure, not exact text.
- pytest; unit tests use fakes for retriever/reranker/provider.
- Public surface re-exported from `rag/pipeline/__init__.py`.

## Dependencies
- `rag/retrieval`, `rag/reranking`, `core/prompting`, `infra/inference_routing`,
  `infra/guardrails`, `infra/tracing`.

## Success criteria
- [ ] `answer(query)` returns a grounded response with citations.
- [ ] Empty/low-relevance retrieval yields a safe "insufficient context" response.
- [ ] Guardrails are applied to the final answer.
- [ ] Tests cover the happy path, empty-retrieval path, and citation presence.

## Open questions
- Citation format and granularity.
- Threshold for declaring "insufficient context".
