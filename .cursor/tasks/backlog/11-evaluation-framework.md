# Module Assignment: Evaluation framework
# Path: src/llm_agents/evaluation/framework/
# Layer: evaluation
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 11 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Provide metrics, a harness to run an agent over a set of cases, and scoring/aggregation
that tolerates LLM non-determinism.

## Background / problem

Without a harness for scoring, "is this better?" is guesswork. Because outputs vary, the
framework must support tolerant/semantic scoring and variance-aware aggregation (multiple
runs) rather than brittle exact matching.

## Scope

### In scope
- A metric interface and a few built-in metrics (e.g. success, tolerant match, latency/cost
  passthrough from tracing).
- A harness that runs an agent/callable over a dataset of cases and collects results.
- Scoring hooks: exact, tolerant/semantic (stub with a seam for LLM-as-judge), rubric.
- Variance-aware aggregation across repeated runs; a structured report.

### Out of scope
- Specific datasets/suites (benchmarking module owns suites).
- Prompt comparison specifics (prompts module).

## Proposed public surface (for Architect to refine)
- `Metric`, `EvalCase`, `EvalHarness`, `Scorer`, `EvalReport`.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- May depend on `core` and `infra`; nothing in `core`/`infra` may depend on this module.
- Non-determinism: aggregation must tolerate variance; avoid exact-match-only scoring.
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `evaluation/framework/__init__.py`.

## Dependencies
- `core/*` (to run agents), `infra/inference_routing`, `infra/tracing`.

## Success criteria
- [ ] A harness runs a (mocked) agent over a case set and computes metrics.
- [ ] Repeated runs aggregate into a variance-aware report.
- [ ] Tolerant scoring works without exact string equality.
- [ ] Tests cover metric computation, harness flow, and aggregation.

## Open questions
- Dataset/case format.
- LLM-as-judge integration and how to bound its cost/variance.
