"""Unit tests for MLflowVersionLogger.

All tests run without a real mlflow installation.
The ``mlflow`` module is patched into sys.modules so that deferred imports
inside ``_get_mlflow`` resolve to a mock — no network calls or tracking server needed.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mlflow_module() -> MagicMock:
    """Return a MagicMock that behaves like the mlflow module.

    Plain MagicMock (no spec) so any attribute access — set_experiment,
    start_run, log_param, set_tag — returns a child MagicMock automatically.
    MagicMock supports the context manager protocol, so
    ``with mlflow.start_run(...): ...`` works without extra setup.
    """
    return MagicMock()


# ---------------------------------------------------------------------------
# Module-level: no mlflow import at top
# ---------------------------------------------------------------------------


class TestMLflowVersionLoggerModuleLevel:
    def test_module_importable_without_mlflow(self) -> None:
        saved = sys.modules.pop("mlflow", None)
        try:
            import importlib

            import llm_agents.infra.model_hub._mlflow_version_logger as mod

            importlib.reload(mod)
        except ImportError:
            pytest.fail("Module import must not require mlflow")
        finally:
            if saved is not None:
                sys.modules["mlflow"] = saved

    def test_no_mlflow_top_level_import(self) -> None:
        import ast
        import inspect

        from llm_agents.infra.model_hub import _mlflow_version_logger as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "mlflow":
                assert node.col_offset != 0, "mlflow must not be a top-level import"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "mlflow":
                        assert node.col_offset != 0, "mlflow must not be a top-level import"


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestMLflowVersionLoggerInit:
    def test_default_tracking_uri_none(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        logger = MLflowVersionLogger()
        assert logger._tracking_uri is None

    def test_default_experiment_name(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        logger = MLflowVersionLogger()
        assert logger._experiment_name == "model_hub"

    def test_custom_tracking_uri_stored(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        logger = MLflowVersionLogger(tracking_uri="http://localhost:5000")
        assert logger._tracking_uri == "http://localhost:5000"

    def test_custom_experiment_name_stored(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        logger = MLflowVersionLogger(experiment_name="my-experiment")
        assert logger._experiment_name == "my-experiment"


# ---------------------------------------------------------------------------
# _get_mlflow
# ---------------------------------------------------------------------------


class TestGetMlflow:
    def test_raises_import_error_when_mlflow_missing(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        with patch.dict(sys.modules, {"mlflow": None}):  # type: ignore[dict-item]
            logger = MLflowVersionLogger()
            with pytest.raises(ImportError, match="mlflow"):
                logger._get_mlflow()

    def test_sets_tracking_uri_when_provided(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            logger = MLflowVersionLogger(tracking_uri="http://server:5000")
            logger._get_mlflow()
        fake_mlflow.set_tracking_uri.assert_called_once_with("http://server:5000")

    def test_does_not_set_tracking_uri_when_none(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            logger = MLflowVersionLogger()
            logger._get_mlflow()
        fake_mlflow.set_tracking_uri.assert_not_called()

    def test_sets_experiment(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            logger = MLflowVersionLogger(experiment_name="prod-hub")
            logger._get_mlflow()
        fake_mlflow.set_experiment.assert_called_once_with("prod-hub")

    def test_returns_mlflow_module(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            logger = MLflowVersionLogger()
            result = logger._get_mlflow()
        assert result is fake_mlflow


# ---------------------------------------------------------------------------
# on_register
# ---------------------------------------------------------------------------


class TestOnRegister:
    def test_start_run_called(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_register("my-model", "v1", {})
        fake_mlflow.start_run.assert_called_once()

    def test_run_name_contains_name_and_version(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_register("bert", "v2", {})
        _, kwargs = fake_mlflow.start_run.call_args
        assert "bert" in kwargs["run_name"]
        assert "v2" in kwargs["run_name"]

    def test_logs_model_name_param(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_register("alpha", "v1", {})
        fake_mlflow.log_param.assert_any_call("model_name", "alpha")

    def test_logs_version_param(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_register("alpha", "v3", {})
        fake_mlflow.log_param.assert_any_call("version", "v3")

    def test_logs_action_register(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_register("m", "v1", {})
        fake_mlflow.log_param.assert_any_call("action", "register")

    def test_logs_metadata_keys_with_meta_prefix(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_register("m", "v1", {"backend": "fake", "device": "cpu"})
        fake_mlflow.log_param.assert_any_call("meta.backend", "fake")
        fake_mlflow.log_param.assert_any_call("meta.device", "cpu")

    def test_sets_tags(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_register("m", "v1", {}, tags={"env": "staging", "team": "ml"})
        fake_mlflow.set_tag.assert_any_call("env", "staging")
        fake_mlflow.set_tag.assert_any_call("team", "ml")

    def test_no_tags_no_set_tag_call(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_register("m", "v1", {})
        fake_mlflow.set_tag.assert_not_called()

    def test_metadata_values_coerced_to_str(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_register("m", "v1", {"layers": 12})
        fake_mlflow.log_param.assert_any_call("meta.layers", "12")


# ---------------------------------------------------------------------------
# on_rollback
# ---------------------------------------------------------------------------


class TestOnRollback:
    def test_start_run_called(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_rollback("m", "v2", "v1")
        fake_mlflow.start_run.assert_called_once()

    def test_run_name_contains_model_name(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_rollback("bert", "v2", "v1")
        _, kwargs = fake_mlflow.start_run.call_args
        assert "bert" in kwargs["run_name"]

    def test_logs_model_name_param(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_rollback("alpha", "v2", "v1")
        fake_mlflow.log_param.assert_any_call("model_name", "alpha")

    def test_logs_from_version(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_rollback("m", "v2", "v1")
        fake_mlflow.log_param.assert_any_call("from_version", "v2")

    def test_logs_to_version(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_rollback("m", "v2", "v1")
        fake_mlflow.log_param.assert_any_call("to_version", "v1")

    def test_logs_action_rollback(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_rollback("m", "v2", "v1")
        fake_mlflow.log_param.assert_any_call("action", "rollback")

    def test_from_version_none_logged_as_unversioned(self) -> None:
        from llm_agents.infra.model_hub._mlflow_version_logger import MLflowVersionLogger

        fake_mlflow = _make_mlflow_module()
        with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
            MLflowVersionLogger().on_rollback("m", None, "v1")
        fake_mlflow.log_param.assert_any_call("from_version", "unversioned")
