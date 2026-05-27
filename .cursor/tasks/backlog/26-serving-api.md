# Module Assignment: Serving API
# Path: src/llm_agents/serving/api/
# Layer: serving
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 26

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Expose orchestration, RAG, and chat over HTTP via FastAPI, wiring the core/rag/infra
subsystems into stateless endpoints.

## Background / problem

The platform needs a runtime entry point. A FastAPI app turns the assembled subsystems into
a deployable service (replacing the placeholder Docker `CMD`).

## Scope

### In scope
- A FastAPI app factory and routers: chat/completion, RAG answer, health/readiness.
- Dependency wiring from `config.py` (model hub, routing, RAG pipeline, guardrails).
- Request/response schemas; tracing per request; structured error responses.
- Stateless handlers (state lives in external memory/vector stores).

### Out of scope
- Auth/rate-limiting infrastructure (separate request) beyond a seam.
- Front-end/UI.

## Proposed public surface (for Architect to refine)
- `create_app()` returning a FastAPI instance; route modules.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- FastAPI/uvicorn behind the `serving` extra; no heavy imports at module top level.
- pytest; use FastAPI's test client with mocked subsystems — no real model/network calls.
- Public surface re-exported from `serving/api/__init__.py`.

## Dependencies
- `core/*`, `rag/pipeline`, `infra/inference_routing`, `infra/guardrails`, `infra/tracing`,
  `config.py`.

## Success criteria
- [ ] App exposes chat, RAG-answer, and health endpoints.
- [ ] Handlers are stateless and wired from config.
- [ ] Tests exercise endpoints via the test client with mocked subsystems.

## Open questions
- Sync vs async endpoints (ties to the routing client decision).
- Streaming responses now or later?
