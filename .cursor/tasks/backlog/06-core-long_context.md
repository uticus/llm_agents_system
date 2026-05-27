# Module Assignment: Long-context handling
# Path: src/llm_agents/core/long_context/
# Layer: core
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 6 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Fit oversized inputs into a model's context window via token counting, chunking,
summarization, and budget-aware packing.

## Background / problem

Real inputs routinely exceed context windows. The system needs deterministic chunking, a
summarization pipeline, and a way to pack the most relevant content into a token budget
before calling a model.

## Scope

### In scope
- Token counting behind an abstraction (pluggable tokenizer).
- Chunking strategies (by tokens/structure) that are deterministic given inputs.
- A summarization pipeline (e.g. map-reduce / refine) that calls models via
  `infra/inference_routing`.
- Budget-aware packing/selection to fit a target token budget; overflow handling.

### Out of scope
- Provider-specific tokenizer implementations beyond one default behind the abstraction.
- Retrieval index/storage (memory module owns long-term storage).

## Proposed public surface (for Architect to refine)
- `count_tokens`, `chunk(text, ...)`, `Summarizer`, `pack_to_budget(items, budget)`.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- Chunking must be deterministic; summarization calls go through the mockable provider boundary.
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `core/long_context/__init__.py`.

## Dependencies
- `infra/inference_routing` (summarization), `infra/tracing`.

## Success criteria
- [ ] A large input is reduced to fit a target budget.
- [ ] Chunk boundaries are deterministic for the same input.
- [ ] Summarization is exercised with a mocked provider.
- [ ] Tests cover chunking, budget fit, and overflow handling.

## Open questions
- Default tokenizer source and how to approximate provider tokenization.
- How summarization quality is evaluated (ties into the evaluation layer).
