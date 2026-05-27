# Module Assignment: Guardrails
# Path: src/llm_agents/infra/guardrails/
# Layer: infra
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 15

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Restrict outputs to compliant domains, limit hallucinations, and enforce tone — via
lightweight regex/embedding filters with an optional NeMo Guardrails adapter.

## Background / problem

Generated text can leak sensitive/roadmap content, drift off-domain, or break tone. A
guardrails layer validates inputs/outputs before they reach the user.

## Scope

### In scope
- A `Guard`/filter interface and a chain that runs input and output checks.
- Default filters: regex/keyword blocklists and an embedding-similarity filter
  (on-domain / off-domain).
- Actions on violation: block, redact, or rewrite-request.
- An optional NeMo Guardrails adapter behind an extra.

### Out of scope
- Policy authoring UI.
- The model calls themselves (owned by routing/model_hub).

## Proposed public surface (for Architect to refine)
- `Guard` (protocol), `GuardrailChain`, built-in `RegexFilter`, `EmbeddingFilter`.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- Default filters depend on nothing heavy; NeMo behind an extra.
- pytest; unit tests must not make real network/model calls.
- Public surface re-exported from `infra/guardrails/__init__.py`.

## Dependencies
- `infra/tracing`. Soft: `rag/embeddings` (for embedding filters), `infra/inference_routing`.

## Success criteria
- [ ] A guardrail chain blocks/redacts violating content and passes compliant content.
- [ ] Regex and embedding filters both work behind the same interface.
- [ ] Tests cover block, redact, and pass paths.

## Open questions
- Where guardrails sit in the request flow (input-only, output-only, or both)?
- How violations are surfaced/logged for audit.
