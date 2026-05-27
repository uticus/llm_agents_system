# Module Assignment: Observability
# Path: src/llm_agents/infra/observability/
# Layer: infra
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 2 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Expose metrics and structured logging for running agent systems, derived where possible
from tracing spans, and exportable to the bundled Prometheus/Grafana stack.

## Background / problem

Per-call spans tell a single story; aggregate metrics (token usage, latency, cost, error
rate) tell the operational story. Operators need queryable metrics and structured logs
correlated with traces.

## Scope

### In scope
- Metric primitives: counter, gauge, histogram, with a registry.
- Structured logger emitting JSON, including the active trace/span id for correlation.
- Derivation of standard metrics from tracing span attributes (tokens, latency, cost, errors).
- A Prometheus-compatible export path aligned with `configs/observability/`.

### Out of scope
- Grafana dashboard contents (config wiring only).
- Alerting rules.
- The tracing model itself (owned by `infra/tracing`).

## Proposed public surface (for Architect to refine)
- `MetricsRegistry`, `Counter`/`Gauge`/`Histogram`, `get_logger(name)`, and a span->metrics
  bridge.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `infra/observability/__init__.py`.
- Metric naming follows a documented convention (define it in the design phase).

## Dependencies
- `infra/tracing` (reads span attributes for metric derivation).

## Success criteria
- [ ] Counters/gauges/histograms record and can be read/exported.
- [ ] Logs are structured and carry the current trace/span id.
- [ ] Metrics can be derived from a completed trace.
- [ ] Tests cover metric updates, log fields, and the span->metrics bridge.

## Open questions
- Pull (Prometheus scrape) vs push (OTLP) as the primary export path?
- Standard metric/label naming convention and cardinality limits.
