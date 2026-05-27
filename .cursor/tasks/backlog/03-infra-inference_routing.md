# Module Assignment: Inference routing
# Path: src/llm_agents/infra/inference_routing/
# Layer: infra
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 3 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Provide a uniform LLM client that routes requests across providers and models by policy,
with retries, backoff, and failover, behind a single mockable boundary.

## Background / problem

Hosted inference is the dominant cost/latency driver and a source of vendor lock-in.
A single routing layer gives every other subsystem one place to call, one place to mock in
tests, and one place to implement policy (cost/capability-based selection, fallbacks).

## Scope

### In scope
- A provider adapter interface plus a uniform request/response model.
- A routing policy: default model, ordered fallbacks, and selection by cost/capability.
- Retry with backoff and rate-limit handling; failover to the next provider/model on error.
- Tracing spans emitted per request (model, tokens, latency, cost, error).
- A fake/in-memory provider for tests.

### Out of scope
- Concrete vendor SDK adapters beyond one reference adapter (others are follow-up requests).
- Streaming responses (future improvement).
- Caching/batching (owned by `cost_latency_optimization`).

## Proposed public surface (for Architect to refine)
- `LLMRequest`, `LLMResponse`, `Provider` (adapter protocol), `Router`, `RoutingPolicy`.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- External LLM APIs only; this is the provider boundary the rest of the system mocks.
- pytest; unit tests use the fake provider, never real network calls.
- Non-determinism: do not assert exact-match on model outputs.
- Public surface re-exported from `infra/inference_routing/__init__.py`.

## Dependencies
- `infra/tracing`.

## Success criteria
- [ ] A request is routed to a model chosen by policy.
- [ ] On provider failure the router falls back and/or retries with backoff.
- [ ] The provider boundary is fully mockable; tests cover policy, fallback, and retry.

## Open questions
- Synchronous now with an async path later, or async-first from the start?
- Which provider gets the reference adapter first?
