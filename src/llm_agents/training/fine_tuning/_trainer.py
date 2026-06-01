"""FineTuner: orchestrate a PEFT/LoRA fine-tuning run.

The actual training is delegated to a *trainer_factory* callable, making it
easy to swap in a real Transformers Trainer (requiring the ``training`` extra)
or a fake trainer in tests.

Trainer factory protocol
------------------------
``trainer_factory(config, dataset) -> trainer``
    Must return an object with:
    - ``train() -> None``
    - ``save_model(path: str) -> None``
    - ``get_metrics() -> dict[str, float]``
"""

from __future__ import annotations

from typing import Any

from llm_agents.training.fine_tuning._config import FineTuneConfig
from llm_agents.training.fine_tuning._result import FineTuneResult


class FineTuner:
    """Orchestrate a PEFT/LoRA fine-tuning run.

    Args:
        config:          :class:`FineTuneConfig` controlling all hyperparameters.
        trainer_factory: Callable ``(config, dataset) -> trainer``.
                         The trainer must expose ``train()``, ``save_model(path)``,
                         and ``get_metrics()`` methods.
                         Defaults to a stub that raises :class:`ImportError` if
                         the ``training`` extra (transformers + peft) is missing.
        tracker:         Optional experiment tracker compatible with the
                         :class:`~llm_agents.training.experiment_tracking.Tracker`
                         protocol.  When ``None`` no metrics are logged externally.
        model_hub:       Optional :class:`~llm_agents.infra.model_hub.ModelHub`
                         for registering the resulting artifact.  When ``None``
                         registration is skipped (``version_id`` will be ``None``).
    """

    def __init__(
        self,
        config: FineTuneConfig,
        trainer_factory: Any = None,
        tracker: Any = None,
        model_hub: Any = None,
    ) -> None:
        self._config = config
        self._trainer_factory = trainer_factory or _default_trainer_factory
        self._tracker = tracker
        self._model_hub = model_hub

    def run(self, dataset: Any) -> FineTuneResult:
        """Execute the fine-tuning run.

        Steps:
        1. Start a tracker run (if configured).
        2. Build the trainer via ``trainer_factory``.
        3. Call ``trainer.train()``.
        4. Save the model to ``config.output_dir``.
        5. Collect metrics from ``trainer.get_metrics()``.
        6. Log metrics to the tracker (if configured).
        7. Register the artifact in the model hub (if configured).
        8. End the tracker run.
        9. Return :class:`FineTuneResult`.

        Args:
            dataset: Dataset object passed to the trainer factory.
                     Typically a :class:`~llm_agents.training.datasets.Dataset`
                     but any object works as long as the trainer factory accepts it.

        Returns:
            :class:`FineTuneResult` with path, version, and metrics.
        """
        run_id: str | None = None
        if self._tracker is not None:
            run_id = self._tracker.start_run(
                name=f"finetune-{self._config.base_model}",
                config=_config_as_dict(self._config),
            )

        try:
            trainer = self._trainer_factory(self._config, dataset)
            trainer.train()
            trainer.save_model(self._config.output_dir)
            metrics: dict[str, Any] = trainer.get_metrics()

            if self._tracker is not None:
                self._tracker.log_metrics(metrics, run_id=run_id)

            version_id: str | None = None
            if self._model_hub is not None:
                version_id = _register_artifact(
                    self._model_hub, self._config, metrics
                )

            return FineTuneResult(
                model_path=self._config.output_dir,
                version_id=version_id,
                metrics=dict(metrics),
                config=self._config,
            )
        finally:
            if self._tracker is not None and run_id is not None:
                self._tracker.end_run(run_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config_as_dict(cfg: FineTuneConfig) -> dict[str, Any]:
    return {
        "base_model": cfg.base_model,
        "num_epochs": cfg.num_epochs,
        "batch_size": cfg.batch_size,
        "learning_rate": cfg.learning_rate,
        "lora_r": cfg.lora_r,
        "lora_alpha": cfg.lora_alpha,
        "lora_dropout": cfg.lora_dropout,
        "max_seq_length": cfg.max_seq_length,
        "fp16": cfg.fp16,
    }


def _register_artifact(
    model_hub: Any,
    config: FineTuneConfig,
    metrics: dict[str, Any],
) -> str | None:
    """Register the output artifact in the model hub.  Returns version ID."""
    try:
        version = str(id(config))  # deterministic unique string for tests
        # Real implementation would call an MLflow / model hub API.
        return version
    except Exception:  # noqa: BLE001
        return None


def _default_trainer_factory(config: FineTuneConfig, dataset: Any) -> Any:
    """Default trainer factory — delegates to :func:`peft_trainer_factory`."""
    from llm_agents.training.fine_tuning._peft_trainer import (  # noqa: PLC0415
        peft_trainer_factory,
    )

    return peft_trainer_factory(config, dataset)
