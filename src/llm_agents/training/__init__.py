"""Offline training and MLOps.

Parameter-efficient fine-tuning with experiment tracking and data/version management.

Subsystems:
    fine_tuning           Transformers + PEFT fine-tuning runs
    datasets              annotation (Prodigy) and storage (Delta Lake / DVC)
    experiment_tracking   MLflow / Weights & Biases / DVC integration

Offline layer: depends on infra/model_hub and data; nothing in the runtime path depends
on it. Requires the ``training`` extra.
"""

__all__ = [
    "fine_tuning",
    "datasets",
    "experiment_tracking",
]
