# Module Assignment: Cost/latency optimization
# Path: src/llm_agents/infra/cost_latency_optimization/
# Layer: infra
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 4 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Reduce spend and latency through opt-in completion caching, request batching, model-tier
selection hints, and per-request budget tracking.

## Background / problem

Spend scales with tokens times calls. Naive systems re-pay for identical work and send
everything to the most expensive model. This module keeps cost sub-linear to traffic while
making the staleness/cost tradeoff explicit and opt-in.

## Scope

### In scope
- Completion cache keyed on prompt + parameters, with an in-memory backend; opt-in per call.
- Request batching for calls that can be grouped.
- Model-tier selection hints feeding `inference_routing` policy.
- Per-request budget tracking (tokens and estimated cost) with reporting.

### Out of scope
- Distributed/shared cache backends (future).
- Hard multi-tenant budget enforcement (future).
- The routing/provider mechanics themselves (owned by `inference_routing`).

## Proposed public surface (for Architect to refine)
- `CompletionCache` (pluggable backend), `Batcher`, `BudgetTracker`, tier-selection helper.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- Caching of probabilistic outputs is opt-in and must be easy to bypass.
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `infra/cost_latency_optimization/__init__.py`.

## Dependencies
- `infra/inference_routing` (augments/wraps it), `infra/tracing`.

## Success criteria
- [ ] A cache hit avoids a provider call; a miss falls through to routing.
- [ ] Batching groups eligible calls and preserves per-call results.
- [ ] Budget tracking accounts tokens/cost per request.
- [ ] Tests cover hit/miss, cache bypass, batching, and budget accounting.

## Open questions
- Cache key: exact match vs semantic similarity? Invalidation policy?
- Where is per-request budget surfaced to the caller?
