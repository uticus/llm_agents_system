"""MLflow-backed Tracker implementation.

:class:`MLflowTracker` satisfies the :class:`Tracker` protocol and delegates
all calls to the MLflow tracking API.  All imports of ``mlflow`` are deferred
to :meth:`_get_mlflow` — the class is importable without the ``training``
extra installed.

Usage::

    from llm_agents.training.experiment_tracking import MLflowTracker

    tracker = MLflowTracker(
        tracking_uri="http://localhost:5000",
        experiment_name="my-experiment",
    )
    run_id = tracker.start_run("finetune-run-1", config={"lr": 2e-4, "epochs": 3})
    tracker.log_metrics({"train_loss": 0.35}, run_id=run_id)
    tracker.end_run(run_id)
"""

from __future__ import annotations

from typing import Any


class MLflowTracker:
    """Production experiment tracker backed by MLflow.

    Satisfies the :class:`~llm_agents.training.experiment_tracking.Tracker`
    protocol without inheriting from it.

    A single MLflow run is active at a time per tracker instance.  Concurrent
    runs in one process require separate :class:`MLflowTracker` instances.

    Args:
        tracking_uri:    MLflow tracking server URI (e.g.
                         ``"http://localhost:5000"``).  When ``None``, the
                         MLflow default (``./mlruns`` or ``MLFLOW_TRACKING_URI``
                         env var) is used.
        experiment_name: MLflow experiment name.  The experiment is created if
                         it does not already exist.
    """

    def __init__(
        self,
        tracking_uri: str | None = None,
        experiment_name: str = "default",
    ) -> None:
        self._tracking_uri = tracking_uri
        self._experiment_name = experiment_name

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_mlflow(self) -> Any:
        """Import and configure mlflow; raise ImportError if not installed."""
        try:
            import mlflow  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "mlflow is required for MLflowTracker. "
                "Install it with: pip install 'llm-agents-system[training]'"
            ) from exc
        if self._tracking_uri is not None:
            mlflow.set_tracking_uri(self._tracking_uri)
        mlflow.set_experiment(self._experiment_name)
        return mlflow

    # ------------------------------------------------------------------
    # Tracker protocol
    # ------------------------------------------------------------------

    def start_run(
        self,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Start a new MLflow run and return its run ID.

        Creates (or resumes) an MLflow experiment named
        :attr:`experiment_name`, starts a run with *name* as the run name,
        and logs all entries in *config* as MLflow params (values are
        stringified).

        Args:
            name:   Human-readable run name.
            config: Optional hyperparameter dict to log as MLflow params.

        Returns:
            MLflow run ID string.
        """
        mlflow = self._get_mlflow()
        run = mlflow.start_run(run_name=name)
        run_id: str = run.info.run_id
        if config:
            mlflow.log_params({k: str(v) for k, v in config.items()})
        return run_id

    def log_metrics(
        self,
        metrics: dict[str, float],
        *,
        run_id: str | None = None,
        step: int | None = None,
    ) -> None:
        """Log scalar metrics to the active MLflow run.

        Args:
            metrics: Metric name -> value mapping.
            run_id:  Accepted for protocol compatibility; the active run is
                     always used — pass ``None`` or the ID returned by
                     :meth:`start_run`.
            step:    Training step or epoch number.  Omitted when ``None``.
        """
        mlflow = self._get_mlflow()
        kwargs: dict[str, Any] = {}
        if step is not None:
            kwargs["step"] = step
        mlflow.log_metrics(metrics, **kwargs)

    def log_params(
        self,
        params: dict[str, Any],
        *,
        run_id: str | None = None,
    ) -> None:
        """Log hyperparameters to the active MLflow run.

        All param values are coerced to strings before logging (MLflow
        requirement).

        Args:
            params: Parameter name -> value mapping.
            run_id: Accepted for protocol compatibility; ignored.
        """
        mlflow = self._get_mlflow()
        mlflow.log_params({k: str(v) for k, v in params.items()})

    def end_run(self, run_id: str) -> None:
        """End the active MLflow run.

        Args:
            run_id: Identifier returned by :meth:`start_run`; accepted for
                    protocol compatibility.
        """
        mlflow = self._get_mlflow()
        mlflow.end_run()
