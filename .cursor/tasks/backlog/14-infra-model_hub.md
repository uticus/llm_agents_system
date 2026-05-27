# Module Assignment: Model hub
# Path: src/llm_agents/infra/model_hub/
# Layer: infra
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 14 (with/just after tracing; before inference_routing depends on it)

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Load and version models across backends behind one `ModelBackend` interface: OpenAI API,
HuggingFace, and GGUF quantized models via llama.cpp and vLLM; track versions via MLflow.

## Background / problem

Different backends have different ops profiles (hosted vs GPU vs CPU/edge). A single hub
lets routing pick the right model per task and keeps versioning consistent.

## Scope

### In scope
- A `ModelBackend` interface (generate, embed where applicable, metadata).
- Reference adapters: OpenAI (default install), and behind extras: HuggingFace,
  llama.cpp (GGUF), vLLM.
- A model registry/catalog with versioning hooks (MLflow).
- Capability/metadata so `inference_routing` can select by cost/capability.

### Out of scope
- Routing policy itself (owned by `inference_routing`).
- Fine-tuning (owned by `training/fine_tuning`).

## Proposed public surface (for Architect to refine)
- `ModelBackend` (protocol), `ModelHub`/registry, adapter classes per backend.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- Local backends behind the `local-inference` extra; HF/MLflow behind `training`. Adapters
  must not import heavy deps at module top level.
- pytest; unit tests use a fake backend, never real models/network.
- Public surface re-exported from `infra/model_hub/__init__.py`.

## Dependencies
- `infra/tracing`.

## Success criteria
- [ ] A model can be resolved and called through `ModelBackend` regardless of backend.
- [ ] At least the OpenAI adapter + a fake backend exist and are tested.
- [ ] Importing the package without extras does not fail.
- [ ] Tests cover backend selection and the fake backend path.

## Open questions
- MLflow registry now vs a thin versioning seam first?
- Sync vs async backend interface.
