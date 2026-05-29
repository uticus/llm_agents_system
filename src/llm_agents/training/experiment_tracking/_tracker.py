"""Tracker protocol and NoOpTracker implementation.

:class:`Tracker` is a structural ``Protocol`` — any class with matching
``start_run``, ``log_metrics``, ``log_params``, and ``end_run`` members
qualifies.

:class:`NoOpTracker` silently discards all calls, useful as a default when
no tracking backend is configured.
"""

from __future__ import annotations

import uuid
from typing import Any

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable


@runtime_checkable
class Tracker(Protocol):
    """Protocol for experiment trackers.

    Any object with matching ``start_run``, ``log_metrics``, ``log_params``,
    and ``end_run`` members satisfies this interface without inheriting.
    """

    def start_run(
        self,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Start a new experiment run.

        Args:
            name:   Human-readable run name.
            config: Optional hyperparameter / configuration dict to log.

        Returns:
            Opaque run identifier used in subsequent calls.
        """
        ...

    def log_metrics(
        self,
        metrics: dict[str, float],
        *,
        run_id: str | None = None,
        step: int | None = None,
    ) -> None:
        """Log scalar metrics for the current (or specified) run.

        Args:
            metrics: Metric name -> value mapping.
            run_id:  Target run ID.  When ``None`` the most recent active run
                     is used.
            step:    Training step or epoch number (optional).
        """
        ...

    def log_params(
        self,
        params: dict[str, Any],
        *,
        run_id: str | None = None,
    ) -> None:
        """Log hyperparameters for the current (or specified) run.

        Args:
            params: Parameter name -> value mapping.
            run_id: Target run ID.
        """
        ...

    def end_run(self, run_id: str) -> None:
        """Mark a run as complete.

        Args:
            run_id: Identifier returned by :meth:`start_run`.
        """
        ...


class NoOpTracker:
    """No-operation tracker that silently discards all calls.

    Useful as a safe default when no external tracking backend is configured.
    All methods accept the same arguments as the :class:`Tracker` protocol
    but do nothing.
    """

    def start_run(
        self,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Return a unique run ID but log nothing."""
        return str(uuid.uuid4())

    def log_metrics(
        self,
        metrics: dict[str, float],
        *,
        run_id: str | None = None,
        step: int | None = None,
    ) -> None:
        """Discard metrics silently."""

    def log_params(
        self,
        params: dict[str, Any],
        *,
        run_id: str | None = None,
    ) -> None:
        """Discard params silently."""

    def end_run(self, run_id: str) -> None:
        """Discard end-run event silently."""


class InMemoryTracker:
    """In-memory tracker that records all calls for test assertions.

    Attributes:
        runs:    List of dicts recording each :meth:`start_run` call.
        metrics: List of dicts recording each :meth:`log_metrics` call.
        params:  List of dicts recording each :meth:`log_params` call.
        ended:   List of run IDs passed to :meth:`end_run`.
    """

    def __init__(self) -> None:
        self.runs: list[dict[str, Any]] = []
        self.metrics: list[dict[str, Any]] = []
        self.params: list[dict[str, Any]] = []
        self.ended: list[str] = []
        self._counter = 0

    def start_run(
        self,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        self._counter += 1
        run_id = f"run-{self._counter}"
        self.runs.append({"id": run_id, "name": name, "config": config or {}})
        return run_id

    def log_metrics(
        self,
        metrics: dict[str, float],
        *,
        run_id: str | None = None,
        step: int | None = None,
    ) -> None:
        self.metrics.append({"run_id": run_id, "step": step, "metrics": dict(metrics)})

    def log_params(
        self,
        params: dict[str, Any],
        *,
        run_id: str | None = None,
    ) -> None:
        self.params.append({"run_id": run_id, "params": dict(params)})

    def end_run(self, run_id: str) -> None:
        self.ended.append(run_id)

    @property
    def run_count(self) -> int:
        return len(self.runs)
