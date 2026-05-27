# Module Assignment: Fine-tuning
# Path: src/llm_agents/training/fine_tuning/
# Layer: training (offline)
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 27
# Implementer: ML

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Run parameter-efficient fine-tuning (Transformers + PEFT) over prepared datasets, logging
runs and registering resulting model versions.

## Background / problem

Fine-tuning adapts a model's style/format (not fresh knowledge — that is RAG). A reproducible
PEFT loop with tracking lets the team iterate on adapters and register them in the model hub.

## Scope

### In scope
- A fine-tuning runner (Transformers + PEFT/LoRA) over a dataset from `training/datasets`.
- Config-driven hyperparameters; logging via `training/experiment_tracking`.
- Output an adapter/model artifact and register a version (MLflow) in `infra/model_hub`.

### Out of scope
- Full pretraining or RLHF.
- Serving the model (owned by `infra/model_hub` + `serving`).

## Proposed public surface (for Architect to refine)
- `FineTuneConfig`, `FineTuner.run(dataset)` -> model/adapter + version id.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- transformers/peft/mlflow behind the `training` extra; no heavy imports at module top level.
- Requires GPU in practice; the module must import without GPU/extra present.
- pytest; unit tests use a tiny fake trainer — no real training in CI.
- Public surface re-exported from `training/fine_tuning/__init__.py`.

## Dependencies
- `training/datasets`, `training/experiment_tracking`, `infra/model_hub`.

## Success criteria
- [ ] A configured run trains over a dataset and produces a registered artifact (fake in CI).
- [ ] Hyperparameters and metrics are logged to the tracker.
- [ ] Tests cover the run flow with a fake trainer.

## Open questions
- Supported base models / adapter types first.
- Where artifacts are stored (MLflow registry vs filesystem).
