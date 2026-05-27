# Module Assignment: Experiment tracking
# Path: src/llm_agents/training/experiment_tracking/
# Layer: training (offline)
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 29

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Track runs, params, metrics, and artifacts behind a `Tracker` interface, with adapters for
MLflow, Weights & Biases, and DVC.

## Background / problem

Fine-tuning and evaluation produce runs that must be comparable and reproducible. One
interface lets the platform switch/add tracking backends without changing call sites.

## Scope

### In scope
- A `Tracker` interface: start/end run, log params/metrics, log artifacts, link model version.
- Adapters: MLflow (default for training), Weights & Biases, DVC (behind extras).
- A no-op tracker for tests/local runs.

### Out of scope
- The training/eval logic that produces the runs.

## Proposed public surface (for Architect to refine)
- `Tracker` (protocol), `MlflowTracker`, `WandbTracker`, `NoOpTracker`.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- mlflow/wandb/dvc behind the `training`/`tracking` extras; no heavy imports at module top level.
- pytest; unit tests use the no-op tracker, never real services.
- Public surface re-exported from `training/experiment_tracking/__init__.py`.

## Dependencies
- None heavy. Used by `training/fine_tuning` and `evaluation/*`.

## Success criteria
- [ ] Runs can be started/ended with params, metrics, and artifacts logged behind the interface.
- [ ] A no-op tracker satisfies the same contract for tests.
- [ ] Tests cover the run lifecycle with the no-op tracker.

## Open questions
- MLflow as the single default vs supporting multiple concurrently.
- How model-version links flow to `infra/model_hub`.
