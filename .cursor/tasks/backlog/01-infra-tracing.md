# Module Assignment: Tracing system
# Path: src/llm_agents/infra/tracing/
# Layer: infra
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 1 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline
> (Analyst -> Decomposer -> Architect -> ...). The "proposed public surface" below is a
> hint to orient the Architect; the final design is decided in the pipeline's design
> phase, not here.

## Goal

Provide structured tracing for every agent, tool, and LLM call: a nestable span model
that produces a serializable trace tree with timing and attributes.

## Background / problem

When an agent misbehaves you need to see why, across many nested calls. Tracing is the
foundation other subsystems build on: observability derives metrics from spans, and
replay_analysis loads recorded traces. Defining the span/trace schema first unblocks both.

## Scope

### In scope
- Span and Trace data model (id, parent id, name, start/end, status, attributes).
- A way to open/close spans: context manager and/or decorator, with automatic parent-child
  nesting via a current-span context.
- Standard attributes for LLM calls: model, prompt/response token counts, latency, cost,
  error.
- In-memory trace collector and a serialize/deserialize path (JSON) for storage and replay.
- A pluggable export hook (so an OpenTelemetry exporter can be added later).

### Out of scope
- Full OpenTelemetry SDK integration (a later improvement; keep an export seam).
- Any UI or visualization.
- Metric aggregation (that is the observability module).

## Proposed public surface (for Architect to refine)
- `Tracer`, `Span`, a `@traced` decorator / `span(name, **attrs)` context manager,
  `current_span()`, and a trace (de)serialization helper.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- I/O-bound system: no hot-path/no-allocation constraints.
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `infra/tracing/__init__.py`.
- Trace serialization must be versioned so replay_analysis can evolve safely.

## Dependencies
- None (foundational). Defines the trace schema consumed by observability and
  replay_analysis.

## Success criteria
- [ ] A nested sequence of calls produces a correct parent-child trace tree.
- [ ] Spans capture timing and arbitrary attributes (incl. the LLM-call attributes).
- [ ] A trace round-trips through serialize -> deserialize unchanged.
- [ ] Tests cover nesting, attribute capture, error status, and serialization.

## Open questions
- Adopt OpenTelemetry data model now, or a minimal internal model with an OTel adapter later?
- Where are traces stored for replay (filesystem fixtures vs a store)?
