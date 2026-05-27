# Module Assignment: Prompt evaluation
# Path: src/llm_agents/evaluation/prompts/
# Layer: evaluation
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 12 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Test, score, and compare prompt variants over a case set, producing a ranked comparison.

## Background / problem

Prompt changes are frequent and their impact is hard to judge by eye. A repeatable A/B
harness over a case set, scored through the evaluation framework, turns prompt iteration
into measurement.

## Scope

### In scope
- A prompt variant model (template + parameters/metadata).
- An A/B(/N) harness that runs each variant over the same cases via `inference_routing`.
- Scoring through `evaluation/framework`; a comparison report that ranks variants.

### Out of scope
- Automatic prompt optimization/search (future).
- The underlying metrics/harness machinery (owned by `evaluation/framework`).

## Proposed public surface (for Architect to refine)
- `PromptVariant`, `PromptComparison`, `compare(variants, cases)`.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- May depend on `core`/`infra` and `evaluation/framework`; not the reverse.
- Non-determinism: ranking must be stable under variance (consider repeats/aggregation).
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `evaluation/prompts/__init__.py`.

## Dependencies
- `evaluation/framework`, `infra/inference_routing`.

## Success criteria
- [ ] Two or more variants are evaluated on the same case set and ranked.
- [ ] The comparison report shows per-variant metrics.
- [ ] Tests with a mocked provider produce a deterministic ranking.

## Open questions
- How to handle statistical significance given output variance.
- Prompt template format and parameter binding.
