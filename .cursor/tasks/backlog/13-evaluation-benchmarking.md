# Module Assignment: Benchmarking
# Path: src/llm_agents/evaluation/benchmarking/
# Layer: evaluation
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 13 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Run agent configurations against task suites and aggregate per-run metrics into a report,
reproducibly via recorded traces. Provide the CLI referenced in the README.

## Background / problem

The README defines a benchmark methodology and a metrics table that is currently unmeasured.
This module implements the harness that fills that table and makes results reproducible by
replaying recorded traces instead of re-calling providers.

## Scope

### In scope
- A suite definition/loader (a set of tasks with expected outcomes).
- A runner producing per-run metrics: task success, tokens/task, latency p50/p95,
  cost/task, cache hit rate.
- Aggregation and a report matching the README benchmark table.
- Reproducibility: a suite can be re-scored from recorded traces (`core/replay_analysis`).
- A CLI entrypoint: `python -m llm_agents.evaluation.benchmarking --suite <name>`.

### Out of scope
- Authoring large real-world suites (separate effort) and publishing numbers.
- Performance tuning of the system under test.

## Proposed public surface (for Architect to refine)
- `Suite`, `BenchmarkRunner`, `BenchmarkReport`, and a `__main__` CLI.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- May depend on `core`/`infra` and `evaluation/framework`; not the reverse.
- Reproducible runs must not call providers (replay from traces).
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `evaluation/benchmarking/__init__.py`.

## Dependencies
- `evaluation/framework`, `core/*` (agents), `core/replay_analysis`,
  `infra/cost_latency_optimization`, `infra/tracing`.

## Success criteria
- [ ] A small suite runs and produces the README metrics (success, tokens, latency, cost,
      cache hit).
- [ ] A suite can be re-scored reproducibly from recorded traces.
- [ ] The CLI runs a named suite and prints/writes a report.
- [ ] Tests cover a tiny suite end-to-end with a mocked provider.

## Open questions
- Where suite content comes from and how baselines are defined.
- Report output format(s): console, JSON, Markdown table.
