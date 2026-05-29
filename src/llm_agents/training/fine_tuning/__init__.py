"""Fine-tuning: parameter-efficient fine-tuning (Transformers + PEFT).

Requires the ``training`` extra.

Public surface
--------------
- :class:`FineTuneConfig` — hyperparameter configuration for a PEFT/LoRA run.
- :class:`FineTuneResult` — output of a completed fine-tuning run.
- :class:`FineTuner` — orchestrates train -> save -> log -> register.
"""

from llm_agents.training.fine_tuning._config import FineTuneConfig
from llm_agents.training.fine_tuning._result import FineTuneResult
from llm_agents.training.fine_tuning._trainer import FineTuner

__all__ = [
    "FineTuneConfig",
    "FineTuneResult",
    "FineTuner",
]
