# Module Assignment: Planning systems
# Path: src/llm_agents/core/planning/
# Layer: core
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 8 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Decompose a goal into executable steps, execute them using memory, tools, and inference,
and replan when a step fails.

## Background / problem

A flat prompt does not scale to multi-step work. Planning turns a goal into an ordered,
inspectable set of steps, drives their execution, and recovers from failures by replanning.

## Scope

### In scope
- A plan/step model (ordered steps, status, results).
- A planner interface with at least two strategies: a simple sequential planner and an
  LLM-driven decomposition planner.
- Step execution wiring to `tool_orchestration` and `inference_routing`, pulling context
  from `agent_memory` and using `long_context` when needed.
- Replanning on step failure.

### Out of scope
- Advanced search strategies (tree-of-thought, graph planning) — future requests.
- The hierarchy/delegation layer (owned by `hierarchical_agents`).

## Proposed public surface (for Architect to refine)
- `Plan`, `Step`, `Planner` (interface), `SequentialPlanner`, `LLMPlanner`, `execute(plan)`.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- LLM calls go through the mockable provider boundary.
- Non-determinism: assert on plan structure/shape, not exact LLM text.
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `core/planning/__init__.py`.

## Dependencies
- `core/agent_memory`, `core/tool_orchestration`, `core/long_context`,
  `infra/inference_routing`, `infra/tracing`.

## Success criteria
- [ ] A planner produces an executable step plan for a goal.
- [ ] Steps execute via tools/LLM with context from memory.
- [ ] A failed step triggers replanning.
- [ ] Tests with a mocked provider yield a deterministic plan structure.

## Open questions
- Concrete plan representation and how much execution autonomy vs caller control.
- How replanning bounds retries to avoid loops.
