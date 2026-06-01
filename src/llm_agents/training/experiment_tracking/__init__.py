"""Experiment tracking: MLflow / Weights & Biases / DVC integration for runs and versions.

Public surface
--------------
- :class:`Tracker` — structural Protocol for experiment trackers.
- :class:`NoOpTracker` — silent no-operation tracker (safe default).
- :class:`InMemoryTracker` — in-memory tracker for test assertions.
- :class:`MLflowTracker` — production tracker backed by MLflow (requires
  the ``training`` extra; all MLflow imports are deferred).
"""

from llm_agents.training.experiment_tracking._mlflow_tracker import MLflowTracker
from llm_agents.training.experiment_tracking._tracker import (
    InMemoryTracker,
    NoOpTracker,
    Tracker,
)

__all__ = [
    "InMemoryTracker",
    "MLflowTracker",
    "NoOpTracker",
    "Tracker",
]
