# Module Assignment: Training datasets
# Path: src/llm_agents/training/datasets/
# Layer: training (offline)
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 28

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Prepare, version, and load training datasets: annotation (Prodigy) import, storage in Delta
Lake / DVC, and a uniform dataset loader for the fine-tuning runner.

## Background / problem

Fine-tuning needs reproducible, versioned data. This module standardizes how annotated data
is imported, stored, versioned, and loaded so runs are repeatable.

## Scope

### In scope
- A dataset model + loader yielding train/val splits to the fine-tuner.
- Import from Prodigy annotation exports.
- Versioned storage seam (Delta Lake / DVC) with a content/version id.
- Basic validation (schema, label distribution).

### Out of scope
- Training itself (owned by `training/fine_tuning`).
- Live annotation tooling.

## Proposed public surface (for Architect to refine)
- `Dataset`, `DatasetLoader`, `from_prodigy(...)`, versioning helpers.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- Delta/DVC/annotation libs behind the `training` extra; no heavy imports at module top level.
- pytest; unit tests use small in-memory fixtures.
- Public surface re-exported from `training/datasets/__init__.py`.

## Dependencies
- Soft: `training/experiment_tracking` (data version linkage).

## Success criteria
- [ ] A dataset loads into train/val splits behind the interface.
- [ ] A Prodigy export imports into the dataset model.
- [ ] Versioning produces a stable id; tests cover load, import, and validation.

## Open questions
- Delta Lake vs DVC as the primary versioning backend.
- Canonical dataset schema across task types.
