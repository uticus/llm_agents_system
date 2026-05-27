# Module Assignment: Tool orchestration
# Path: src/llm_agents/core/tool_orchestration/
# Layer: core
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 7 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Let agents register tools and have model-requested tool calls dispatched, validated,
executed, and returned safely without crashing the run.

## Background / problem

Agents must call external tools, but model-driven dispatch is error-prone: arguments may be
malformed and tools may fail. A registry + dispatcher with validation and error capture
makes tool use safe and observable.

## Scope

### In scope
- A tool definition (name, description, argument schema, callable).
- A registry to register/look up tools.
- A dispatcher that maps a model tool-call to an execution, validates arguments, runs the
  tool, and formats the result back for the model.
- Error capture: tool failures are surfaced as structured results, not exceptions that
  abort the agent.
- A tracing span per tool invocation.

### Out of scope
- Specific built-in tool implementations (separate requests).
- Provider-specific tool-calling wire formats beyond an adapter seam.

## Proposed public surface (for Architect to refine)
- `Tool`, `ToolRegistry`, `ToolDispatcher`, `ToolResult`.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- Argument validation at the boundary; invalid calls produce structured errors.
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `core/tool_orchestration/__init__.py`.

## Dependencies
- `infra/tracing`.

## Success criteria
- [ ] A tool can be registered and dispatched by name with validated arguments.
- [ ] Invalid arguments yield a structured error, not an unhandled exception.
- [ ] A failing tool is captured and reported without aborting the run.
- [ ] Tests cover dispatch, validation failure, and error handling.

## Open questions
- Argument schema format (JSON Schema?) and alignment with provider tool-calling formats.
- Sync vs async tool execution.
