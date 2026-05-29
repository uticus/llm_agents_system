"""FineTuneConfig: hyperparameters for a PEFT/LoRA fine-tuning run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FineTuneConfig:
    """Hyperparameter configuration for a fine-tuning run.

    Args:
        base_model:    Base model identifier (HuggingFace hub name or local path).
        output_dir:    Directory to write the trained adapter/model.
        num_epochs:    Number of training epochs.
        batch_size:    Per-device training batch size.
        learning_rate: AdamW learning rate.
        lora_r:        LoRA rank (adapter size).
        lora_alpha:    LoRA scaling factor.
        lora_dropout:  Dropout probability applied to LoRA layers.
        max_seq_length: Maximum token sequence length.
        fp16:          Use fp16 mixed-precision when ``True``.
        extra:         Additional provider-specific key-value overrides.
    """

    base_model: str
    output_dir: str = "output"
    num_epochs: int = 1
    batch_size: int = 4
    learning_rate: float = 2e-4
    lora_r: int = 8
    lora_alpha: int = 32
    lora_dropout: float = 0.1
    max_seq_length: int = 512
    fp16: bool = False
    extra: dict[str, Any] = field(default_factory=dict)
