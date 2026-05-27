# Module Assignment: Replay-analysis agents
# Path: src/llm_agents/core/replay_analysis/
# Layer: core
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 10 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Load recorded run traces and replay them deterministically (without calling providers) to
analyze timing, cost, errors, and behavior.

## Background / problem

LLM outputs are non-deterministic, so reproducibility comes from recorded traces, not
identical outputs. Replaying a recorded trace lets you debug and re-score a run offline and
detect divergence, which is the backbone of the project's reproducibility story.

## Scope

### In scope
- Load a trace using the schema defined by `infra/tracing`.
- A replay engine that re-runs/re-scores a run from recorded provider responses, making no
  live provider calls.
- Analysis outputs: timeline, cost/token breakdown, error locations, and divergence
  detection between a recorded and a fresh run.
- Sample trace fixtures under `tests/fixtures/traces/`.

### Out of scope
- A live debugging UI.
- The tracing capture model itself (owned by `infra/tracing`).

## Proposed public surface (for Architect to refine)
- `load_trace(path)`, `ReplayEngine`, `analyze(trace)` returning a structured report.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- Replay must be deterministic and must not make real network calls.
- pytest; tests use recorded fixtures.
- Public surface re-exported from `core/replay_analysis/__init__.py`.

## Dependencies
- `infra/tracing` (trace schema). Soft: `evaluation/framework` (re-scoring).

## Success criteria
- [ ] A recorded trace loads and replays deterministically with no provider calls.
- [ ] Analysis produces a timeline plus cost/error summary.
- [ ] Divergence between recorded and fresh runs can be detected.
- [ ] Tests run against a committed sample trace fixture.

## Open questions
- Trace storage format and versioning/compatibility guarantees.
- What "replay fidelity" guarantees we make when code under test changes.
