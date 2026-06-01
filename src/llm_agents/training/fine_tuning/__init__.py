"""Fine-tuning: parameter-efficient fine-tuning (Transformers + PEFT).

Requires the ``training`` extra.

Public surface
--------------
- :class:`FineTuneConfig` — hyperparameter configuration for a PEFT/LoRA run.
- :class:`FineTuneResult` — output of a completed fine-tuning run.
- :class:`FineTuner` — orchestrates train -> save -> log -> register.
- :class:`PeftTrainer` — HuggingFace Trainer wrapper; exposes the trainer
  protocol used by :class:`FineTuner`.
- :func:`peft_trainer_factory` — default ``trainer_factory``; builds a
  :class:`PeftTrainer` from a :class:`FineTuneConfig` + dataset.
"""

from llm_agents.training.fine_tuning._config import FineTuneConfig
from llm_agents.training.fine_tuning._peft_trainer import PeftTrainer, peft_trainer_factory
from llm_agents.training.fine_tuning._result import FineTuneResult
from llm_agents.training.fine_tuning._trainer import FineTuner

__all__ = [
    "FineTuneConfig",
    "FineTuneResult",
    "FineTuner",
    "PeftTrainer",
    "peft_trainer_factory",
]
