"""PEFT/QLoRA trainer implementation for FineTuner.

``PeftTrainer`` wraps a HuggingFace ``Trainer`` and exposes the three-method
trainer protocol expected by :class:`~llm_agents.training.fine_tuning.FineTuner`:
``train()``, ``save_model(path)``, and ``get_metrics()``.

``peft_trainer_factory`` is the default ``trainer_factory`` used by
:class:`FineTuner` when the ``training`` extra is installed.  All imports
from ``transformers`` and ``peft`` are deferred to that function — the module
is importable and ``PeftTrainer`` is instantiable without those packages.
"""

from __future__ import annotations

from typing import Any

from llm_agents.training.fine_tuning._config import FineTuneConfig

# Keys that appear in HuggingFace log_history but are not training metrics.
_LOG_SKIP: frozenset[str] = frozenset({"step", "epoch", "learning_rate"})


class PeftTrainer:
    """Wraps a HuggingFace ``Trainer``; exposes the FineTuner trainer protocol.

    Protocol methods
    ----------------
    ``train() -> None``
        Delegates to the wrapped ``Trainer.train()``.
    ``save_model(path: str) -> None``
        Delegates to ``Trainer.save_model(path)``.
    ``get_metrics() -> dict[str, float]``
        Merges ``TrainOutput.metrics`` with scalar entries from
        ``Trainer.state.log_history``.
    """

    def __init__(self, hf_trainer: Any) -> None:
        self._trainer = hf_trainer
        self._train_output: Any = None

    # ------------------------------------------------------------------
    # Trainer protocol
    # ------------------------------------------------------------------

    def train(self) -> None:
        """Execute the training loop via the wrapped HuggingFace Trainer."""
        self._train_output = self._trainer.train()

    def save_model(self, path: str) -> None:
        """Persist the trained adapter / full model to *path*."""
        self._trainer.save_model(path)

    def get_metrics(self) -> dict[str, float]:
        """Return training metrics collected during the last :meth:`train` call.

        Combines ``TrainOutput.metrics`` (if present) with scalar entries from
        ``Trainer.state.log_history``.  Returns an empty dict if :meth:`train`
        has not been called yet.
        """
        result: dict[str, float] = {}

        # Metrics attached to the TrainOutput object.
        if self._train_output is not None:
            out_metrics = getattr(self._train_output, "metrics", None) or {}
            for key, val in out_metrics.items():
                if isinstance(val, (int, float)):
                    result[key] = float(val)

        # Scalar entries from the per-step / per-epoch log history.
        state = getattr(self._trainer, "state", None)
        log_history = getattr(state, "log_history", None) or []
        for entry in log_history:
            for key, val in entry.items():
                if key not in _LOG_SKIP and isinstance(val, (int, float)):
                    result[key] = float(val)

        return result


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def peft_trainer_factory(config: FineTuneConfig, dataset: Any) -> PeftTrainer:
    """Build a :class:`PeftTrainer` backed by HuggingFace Transformers + PEFT.

    All heavy imports (``transformers``, ``peft``) are deferred to this function.

    Standard LoRA
    ~~~~~~~~~~~~~
    When ``config.use_4bit`` is ``False`` (the default), the base model is
    loaded in full precision and a LoRA adapter is applied via
    ``peft.get_peft_model``.

    QLoRA (4-bit)
    ~~~~~~~~~~~~~
    When ``config.use_4bit`` is ``True``, the base model is loaded in 4-bit
    using ``transformers.BitsAndBytesConfig`` and ``bitsandbytes``.  The model
    is then prepared with ``peft.prepare_model_for_kbit_training`` before the
    LoRA adapter is applied.  Requires ``bitsandbytes`` to be installed
    separately (``pip install bitsandbytes``).

    LoRA target modules
    ~~~~~~~~~~~~~~~~~~~
    Pass ``config.extra["lora_target_modules"]`` as a list of strings to
    restrict LoRA to specific named layers (e.g. ``["q_proj", "v_proj"]``).
    If omitted, PEFT uses its built-in defaults for the model architecture.

    Args:
        config:  Fine-tuning hyperparameters (see :class:`FineTuneConfig`).
        dataset: Training data passed directly to the HuggingFace ``Trainer``
                 as ``train_dataset``.

    Returns:
        :class:`PeftTrainer` wrapping a fully configured HuggingFace
        ``Trainer``.

    Raises:
        ImportError: ``transformers`` is not installed
                     (``training`` extra missing).
        ImportError: ``peft`` is not installed (``training`` extra missing).
        ImportError: ``config.use_4bit=True`` and ``bitsandbytes`` is not
                     installed.
    """
    # ------------------------------------------------------------------
    # Required: transformers
    # ------------------------------------------------------------------
    try:
        from transformers import (  # noqa: PLC0415
            AutoModelForCausalLM,
            AutoTokenizer,
            TrainingArguments,
        )
        from transformers import (
            Trainer as HFTrainer,
        )
    except ImportError as exc:
        raise ImportError(
            "transformers is required for peft_trainer_factory. "
            "Install it with: pip install 'llm-agents-system[training]'"
        ) from exc

    # ------------------------------------------------------------------
    # Required: peft
    # ------------------------------------------------------------------
    try:
        from peft import LoraConfig, TaskType, get_peft_model  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "peft is required for peft_trainer_factory. "
            "Install it with: pip install 'llm-agents-system[training]'"
        ) from exc

    # ------------------------------------------------------------------
    # Optional QLoRA: 4-bit quantization via bitsandbytes
    # ------------------------------------------------------------------
    quantization_config: Any = None
    if config.use_4bit:
        try:
            import bitsandbytes  # noqa: F401, PLC0415
        except ImportError as exc:
            raise ImportError(
                "bitsandbytes is required for QLoRA (use_4bit=True). "
                "Install it with: pip install bitsandbytes"
            ) from exc
        from transformers import BitsAndBytesConfig  # noqa: PLC0415

        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype="float16",
        )

    # ------------------------------------------------------------------
    # Tokenizer
    # ------------------------------------------------------------------
    tokenizer = AutoTokenizer.from_pretrained(config.base_model)
    if getattr(tokenizer, "pad_token", None) is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ------------------------------------------------------------------
    # Base model
    # ------------------------------------------------------------------
    model_kwargs: dict[str, Any] = {}
    if quantization_config is not None:
        model_kwargs["quantization_config"] = quantization_config
    model = AutoModelForCausalLM.from_pretrained(config.base_model, **model_kwargs)

    if config.use_4bit:
        from peft import prepare_model_for_kbit_training  # noqa: PLC0415

        model = prepare_model_for_kbit_training(model)

    # ------------------------------------------------------------------
    # LoRA adapter
    # ------------------------------------------------------------------
    lora_kwargs: dict[str, Any] = {}
    target_modules = config.extra.get("lora_target_modules")
    if target_modules is not None:
        lora_kwargs["target_modules"] = target_modules

    lora_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        task_type=TaskType.CAUSAL_LM,
        **lora_kwargs,
    )
    model = get_peft_model(model, lora_config)

    # ------------------------------------------------------------------
    # Training arguments
    # ------------------------------------------------------------------
    training_args = TrainingArguments(
        output_dir=config.output_dir,
        num_train_epochs=config.num_epochs,
        per_device_train_batch_size=config.batch_size,
        learning_rate=config.learning_rate,
        fp16=config.fp16,
        logging_steps=10,
        save_strategy="no",
        report_to="none",
    )

    # ------------------------------------------------------------------
    # HuggingFace Trainer
    # ------------------------------------------------------------------
    hf_trainer = HFTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
    )

    return PeftTrainer(hf_trainer)
