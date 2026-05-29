"""FineTuneResult: output of a completed fine-tuning run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FineTuneResult:
    """Output produced by :class:`FineTuner.run`.

    Attributes:
        model_path:   Path to the saved adapter / model directory.
        version_id:   Artifact version registered in the model hub / tracker.
                      ``None`` when registration was skipped.
        metrics:      Training metrics logged during the run
                      (e.g. ``{"train_loss": 0.35, "eval_loss": 0.42}``).
        config:       The :class:`FineTuneConfig` used for this run.
    """

    model_path: str
    version_id: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    config: Any = None
