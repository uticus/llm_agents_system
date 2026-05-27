# Module Assignment: Hierarchical agents
# Path: src/llm_agents/core/hierarchical_agents/
# Layer: core
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 9 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Support supervisor/worker hierarchies: a supervisor decomposes a goal, delegates subtasks
to worker agents, and aggregates their results.

## Background / problem

Complex goals benefit from division of labor. A supervisor coordinating specialized workers
scales better and isolates failures, but needs a clear delegation and aggregation protocol.

## Scope

### In scope
- An agent role model (supervisor, worker) with a shared agent interface.
- A supervisor that splits a goal (via `planning`), delegates subtasks to workers, and
  aggregates results.
- A coordination/communication protocol between supervisor and workers.
- Failure handling: a worker failure is surfaced and handled by the supervisor.

### Out of scope
- Arbitrary multi-level network topologies (start with one supervisor + N workers).
- Distributed execution across processes/machines (future).

## Proposed public surface (for Architect to refine)
- `Agent` (interface), `Supervisor`, `Worker`, a delegation/result-aggregation API.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- LLM calls go through the mockable provider boundary.
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `core/hierarchical_agents/__init__.py`.

## Dependencies
- `core/planning`, `core/tool_orchestration`, `core/agent_memory`, `infra/tracing`.

## Success criteria
- [ ] A supervisor decomposes a goal and delegates subtasks to workers.
- [ ] Worker results are aggregated into a final result.
- [ ] A worker failure is handled by the supervisor rather than aborting everything.
- [ ] Tests with mocked workers verify delegation and aggregation.

## Open questions
- Communication medium: shared memory vs explicit messages?
- How failures and partial results propagate up the hierarchy.
