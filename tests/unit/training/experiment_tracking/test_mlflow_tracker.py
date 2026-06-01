"""Unit tests for MLflowTracker.

All tests run without a real mlflow installation.  The ``mlflow`` module is
patched into ``sys.modules`` via ``MagicMock`` so that deferred imports inside
``_get_mlflow`` resolve to controllable mocks.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from llm_agents.training.experiment_tracking import MLflowTracker, Tracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mlflow_mock(run_id: str = "run-abc-123") -> MagicMock:
    """Return a fully configured mock mlflow module."""
    mod = MagicMock()
    run_info = MagicMock()
    run_info.run_id = run_id
    mock_run = MagicMock()
    mock_run.info = run_info
    mod.start_run.return_value = mock_run
    return mod


# ---------------------------------------------------------------------------
# Module-level: no top-level mlflow import
# ---------------------------------------------------------------------------


class TestMLflowTrackerModuleLevel:
    def test_module_importable_without_mlflow(self) -> None:
        saved = sys.modules.pop("mlflow", None)
        try:
            import importlib

            import llm_agents.training.experiment_tracking._mlflow_tracker as mod

            importlib.reload(mod)
        except ImportError:
            pytest.fail("Module must be importable without mlflow")
        finally:
            if saved is not None:
                sys.modules["mlflow"] = saved

    def test_no_top_level_mlflow_import(self) -> None:
        import ast
        import inspect

        from llm_agents.training.experiment_tracking import _mlflow_tracker as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            is_mlflow = isinstance(node, ast.ImportFrom) and (
                (node.module or "").startswith("mlflow")
            )
            if is_mlflow:
                assert node.col_offset != 0, "mlflow must not be a top-level import"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "mlflow" in alias.name:
                        assert node.col_offset != 0, "mlflow must not be a top-level import"


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestMLflowTrackerProtocol:
    def test_isinstance_tracker(self) -> None:
        tracker = MLflowTracker()
        assert isinstance(tracker, Tracker)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestMLflowTrackerInit:
    def test_tracking_uri_stored(self) -> None:
        t = MLflowTracker(tracking_uri="http://localhost:5000")
        assert t._tracking_uri == "http://localhost:5000"

    def test_experiment_name_stored(self) -> None:
        t = MLflowTracker(experiment_name="my-exp")
        assert t._experiment_name == "my-exp"

    def test_defaults(self) -> None:
        t = MLflowTracker()
        assert t._tracking_uri is None
        assert t._experiment_name == "default"


# ---------------------------------------------------------------------------
# _get_mlflow
# ---------------------------------------------------------------------------


class TestMLflowTrackerGetMlflow:
    def test_raises_import_error_when_missing(self) -> None:
        with patch.dict(sys.modules, {"mlflow": None}):  # type: ignore[dict-item]
            t = MLflowTracker()
            with pytest.raises(ImportError, match="mlflow"):
                t._get_mlflow()

    def test_sets_tracking_uri_when_provided(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker(tracking_uri="http://localhost:5000")
            t._get_mlflow()
        mod.set_tracking_uri.assert_called_once_with("http://localhost:5000")

    def test_does_not_set_tracking_uri_when_none(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker(tracking_uri=None)
            t._get_mlflow()
        mod.set_tracking_uri.assert_not_called()

    def test_sets_experiment_name(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker(experiment_name="training-runs")
            t._get_mlflow()
        mod.set_experiment.assert_called_once_with("training-runs")


# ---------------------------------------------------------------------------
# start_run
# ---------------------------------------------------------------------------


class TestMLflowTrackerStartRun:
    def test_returns_run_id(self) -> None:
        mod = _make_mlflow_mock(run_id="run-xyz")
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            run_id = t.start_run("my-run")
        assert run_id == "run-xyz"

    def test_start_run_called_with_run_name(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.start_run("finetune-gpt2")
        mod.start_run.assert_called_once_with(run_name="finetune-gpt2")

    def test_logs_params_from_config(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.start_run("r", config={"lr": 2e-4, "epochs": 3})
        mod.log_params.assert_called_once()
        _, kwargs = mod.log_params.call_args
        # params are passed as positional
        args, _ = mod.log_params.call_args
        logged = args[0]
        assert "lr" in logged
        assert "epochs" in logged

    def test_param_values_are_stringified(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.start_run("r", config={"lr": 2e-4})
        args, _ = mod.log_params.call_args
        assert isinstance(args[0]["lr"], str)

    def test_no_log_params_when_config_none(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.start_run("r", config=None)
        mod.log_params.assert_not_called()

    def test_no_log_params_when_config_empty(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.start_run("r", config={})
        mod.log_params.assert_not_called()


# ---------------------------------------------------------------------------
# log_metrics
# ---------------------------------------------------------------------------


class TestMLflowTrackerLogMetrics:
    def test_log_metrics_called(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.log_metrics({"loss": 0.5})
        mod.log_metrics.assert_called_once()

    def test_metrics_dict_passed(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.log_metrics({"train_loss": 0.42, "eval_loss": 0.50})
        args, _ = mod.log_metrics.call_args
        assert args[0] == {"train_loss": 0.42, "eval_loss": 0.50}

    def test_step_passed_when_provided(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.log_metrics({"loss": 0.3}, step=10)
        _, kwargs = mod.log_metrics.call_args
        assert kwargs.get("step") == 10

    def test_step_omitted_when_none(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.log_metrics({"loss": 0.3}, step=None)
        _, kwargs = mod.log_metrics.call_args
        assert "step" not in kwargs

    def test_run_id_param_accepted(self) -> None:
        """run_id is accepted for protocol compatibility; no error raised."""
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            # Should not raise
            t.log_metrics({"loss": 0.3}, run_id="any-id")


# ---------------------------------------------------------------------------
# log_params
# ---------------------------------------------------------------------------


class TestMLflowTrackerLogParams:
    def test_log_params_called(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.log_params({"batch_size": 8})
        mod.log_params.assert_called_once()

    def test_param_values_stringified(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.log_params({"epochs": 5, "lr": 2e-4})
        args, _ = mod.log_params.call_args
        for v in args[0].values():
            assert isinstance(v, str)

    def test_run_id_param_accepted(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.log_params({"k": "v"}, run_id="any-id")
        mod.log_params.assert_called_once()


# ---------------------------------------------------------------------------
# end_run
# ---------------------------------------------------------------------------


class TestMLflowTrackerEndRun:
    def test_end_run_calls_mlflow_end_run(self) -> None:
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.end_run("run-123")
        mod.end_run.assert_called_once()

    def test_end_run_run_id_not_forwarded_to_mlflow(self) -> None:
        """mlflow.end_run() takes no arguments; run_id is for our protocol only."""
        mod = _make_mlflow_mock()
        with patch.dict(sys.modules, {"mlflow": mod}):
            t = MLflowTracker()
            t.end_run("run-123")
        mod.end_run.assert_called_once_with()
