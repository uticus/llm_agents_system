"""MLflowVersionLogger: log ModelHub register / rollback events to MLflow.

The ``mlflow`` package is a deferred import — this module is importable
without mlflow installed.  The import happens on the first call to
``on_register`` or ``on_rollback``.

Requires the ``training`` extra::

    pip install 'llm-agents-system[training]'
"""

from __future__ import annotations

from typing import Any


class MLflowVersionLogger:
    """Side-effect logger that creates MLflow runs for ModelHub version events.

    Each call to :meth:`on_register` or :meth:`on_rollback` opens a new MLflow
    run, logs structured parameters and tags, then closes the run.

    The ``mlflow`` package is imported lazily: instantiating this class never
    triggers the import.

    Args:
        tracking_uri:    Optional MLflow tracking server URI
                         (e.g. ``"http://localhost:5000"``).
                         When ``None`` the MLflow default is used.
        experiment_name: MLflow experiment to log under.
                         Defaults to ``"model_hub"``.
    """

    def __init__(
        self,
        tracking_uri: str | None = None,
        experiment_name: str = "model_hub",
    ) -> None:
        self._tracking_uri = tracking_uri
        self._experiment_name = experiment_name

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_mlflow(self) -> Any:
        """Return the ``mlflow`` module, applying URI and experiment settings.

        Raises:
            ImportError: If ``mlflow`` is not installed.
        """
        try:
            import mlflow  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "mlflow is required for MLflowVersionLogger. "
                "Install it with: pip install 'llm-agents-system[training]'"
            ) from exc

        if self._tracking_uri is not None:
            mlflow.set_tracking_uri(self._tracking_uri)
        mlflow.set_experiment(self._experiment_name)
        return mlflow

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_register(
        self,
        name: str,
        version: str,
        metadata: dict[str, Any],
        tags: dict[str, str] | None = None,
    ) -> None:
        """Log a model registration event to MLflow.

        Opens a new MLflow run named ``"register-{name}-{version}"``,
        logs ``model_name``, ``version``, ``action="register"``, all
        *metadata* keys as ``meta.<key>`` parameters, and all *tags* as
        MLflow tags.

        Args:
            name:     Backend name (from :attr:`ModelBackend.name`).
            version:  Version string passed to
                      :meth:`~ModelHub.register_version`.
            metadata: Dict returned by :meth:`~ModelBackend.metadata`.
            tags:     Optional key/value pairs to attach as MLflow tags.
        """
        mlflow = self._get_mlflow()
        with mlflow.start_run(run_name=f"register-{name}-{version}"):
            mlflow.log_param("model_name", name)
            mlflow.log_param("version", version)
            mlflow.log_param("action", "register")
            for key, value in (metadata or {}).items():
                mlflow.log_param(f"meta.{key}", str(value))
            for key, value in (tags or {}).items():
                mlflow.set_tag(key, value)

    def on_rollback(
        self,
        name: str,
        from_version: str | None,
        to_version: str,
    ) -> None:
        """Log a rollback event to MLflow.

        Opens a new MLflow run named ``"rollback-{name}"``, logs
        ``model_name``, ``from_version``, ``to_version``, and
        ``action="rollback"``.

        Args:
            name:         Backend name.
            from_version: Version string that was active before the rollback,
                          or ``None`` if the backend had no active version.
            to_version:   Version string that is now active.
        """
        mlflow = self._get_mlflow()
        with mlflow.start_run(run_name=f"rollback-{name}"):
            mlflow.log_param("model_name", name)
            from_v = from_version if from_version is not None else "unversioned"
            mlflow.log_param("from_version", from_v)
            mlflow.log_param("to_version", to_version)
            mlflow.log_param("action", "rollback")
