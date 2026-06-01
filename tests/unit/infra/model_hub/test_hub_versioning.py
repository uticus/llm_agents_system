"""Unit tests for ModelHub versioning API.

Covers register_version, list_versions, active_version, get_version, rollback,
and version_logger integration — all without a real mlflow installation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from llm_agents.infra.model_hub import FakeBackend, ModelHub

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _backend(name: str, tag: str = "r") -> FakeBackend:
    return FakeBackend(name, [tag])


def _make_logger() -> MagicMock:
    """Return a mock version logger with on_register / on_rollback."""
    logger = MagicMock()
    return logger


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestModelHubVersioningInit:
    def test_default_version_logger_none(self) -> None:
        hub = ModelHub()
        assert hub._version_logger is None

    def test_custom_version_logger_stored(self) -> None:
        logger = _make_logger()
        hub = ModelHub(version_logger=logger)
        assert hub._version_logger is logger

    def test_version_state_empty_at_start(self) -> None:
        hub = ModelHub()
        assert hub._versions == {}
        assert hub._version_map == {}
        assert hub._active_versions == {}

    def test_initial_backends_not_versioned(self) -> None:
        b = _backend("init")
        hub = ModelHub(backends={"init": b})
        assert hub.active_version("init") is None
        assert hub.list_versions("init") == []


# ---------------------------------------------------------------------------
# register_version
# ---------------------------------------------------------------------------


class TestRegisterVersion:
    def test_backend_retrievable_via_get(self) -> None:
        hub = ModelHub()
        b = _backend("m")
        hub.register_version(b, "v1")
        assert hub.get("m") is b

    def test_active_version_set(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("m"), "v1")
        assert hub.active_version("m") == "v1"

    def test_second_version_becomes_active(self) -> None:
        hub = ModelHub()
        b1 = _backend("m", "r1")
        b2 = _backend("m", "r2")
        hub.register_version(b1, "v1")
        hub.register_version(b2, "v2")
        assert hub.active_version("m") == "v2"
        assert hub.get("m") is b2

    def test_versions_list_insertion_order(self) -> None:
        hub = ModelHub()
        for v in ["v1", "v2", "v3"]:
            hub.register_version(_backend("m"), v)
        assert hub.list_versions("m") == ["v1", "v2", "v3"]

    def test_overwrite_same_version(self) -> None:
        hub = ModelHub()
        b1 = _backend("m", "old")
        b2 = _backend("m", "new")
        hub.register_version(b1, "v1")
        hub.register_version(b2, "v1")
        assert hub.get_version("m", "v1") is b2
        # list_versions must not duplicate the key
        assert hub.list_versions("m").count("v1") == 1

    def test_get_version_returns_correct_checkpoint(self) -> None:
        hub = ModelHub()
        b1 = _backend("m", "r1")
        b2 = _backend("m", "r2")
        hub.register_version(b1, "v1")
        hub.register_version(b2, "v2")
        assert hub.get_version("m", "v1") is b1
        assert hub.get_version("m", "v2") is b2

    def test_hub_len_counts_unique_names(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("a"), "v1")
        hub.register_version(_backend("a"), "v2")
        hub.register_version(_backend("b"), "v1")
        assert len(hub) == 2

    def test_logger_on_register_called(self) -> None:
        logger = _make_logger()
        hub = ModelHub(version_logger=logger)
        b = _backend("m")
        hub.register_version(b, "v1")
        logger.on_register.assert_called_once()

    def test_logger_on_register_args(self) -> None:
        logger = _make_logger()
        hub = ModelHub(version_logger=logger)
        b = _backend("my-model")
        hub.register_version(b, "v1", tags={"env": "prod"})
        args, kwargs = logger.on_register.call_args
        assert args[0] == "my-model"
        assert args[1] == "v1"
        assert isinstance(args[2], dict)  # metadata dict
        assert args[3] == {"env": "prod"}

    def test_no_logger_no_error(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("m"), "v1")  # must not raise

    def test_tags_default_empty_dict(self) -> None:
        logger = _make_logger()
        hub = ModelHub(version_logger=logger)
        hub.register_version(_backend("m"), "v1")  # no tags kwarg
        args, _ = logger.on_register.call_args
        assert args[3] == {}

    def test_multiple_backends_tracked_independently(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("a"), "v1")
        hub.register_version(_backend("b"), "v2")
        assert hub.active_version("a") == "v1"
        assert hub.active_version("b") == "v2"


# ---------------------------------------------------------------------------
# list_versions / active_version / get_version
# ---------------------------------------------------------------------------


class TestVersionQueries:
    def test_list_versions_empty_for_unknown_name(self) -> None:
        hub = ModelHub()
        assert hub.list_versions("unknown") == []

    def test_active_version_none_for_unknown_name(self) -> None:
        hub = ModelHub()
        assert hub.active_version("unknown") is None

    def test_get_version_none_for_unknown_name(self) -> None:
        hub = ModelHub()
        assert hub.get_version("unknown", "v1") is None

    def test_get_version_none_for_unknown_version(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("m"), "v1")
        assert hub.get_version("m", "v99") is None

    def test_list_versions_returns_copy(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("m"), "v1")
        lst = hub.list_versions("m")
        lst.append("injected")
        assert hub.list_versions("m") == ["v1"]


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


class TestRollback:
    def test_rollback_restores_backend(self) -> None:
        hub = ModelHub()
        b1 = _backend("m", "r1")
        b2 = _backend("m", "r2")
        hub.register_version(b1, "v1")
        hub.register_version(b2, "v2")
        hub.rollback("m", "v1")
        assert hub.get("m") is b1

    def test_rollback_updates_active_version(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("m"), "v1")
        hub.register_version(_backend("m"), "v2")
        hub.rollback("m", "v1")
        assert hub.active_version("m") == "v1"

    def test_rollback_returns_true_on_success(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("m"), "v1")
        hub.register_version(_backend("m"), "v2")
        assert hub.rollback("m", "v1") is True

    def test_rollback_returns_false_unknown_name(self) -> None:
        hub = ModelHub()
        assert hub.rollback("nonexistent", "v1") is False

    def test_rollback_returns_false_unknown_version(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("m"), "v1")
        assert hub.rollback("m", "v99") is False

    def test_rollback_does_not_alter_version_list(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("m"), "v1")
        hub.register_version(_backend("m"), "v2")
        hub.rollback("m", "v1")
        assert hub.list_versions("m") == ["v1", "v2"]

    def test_rollback_calls_logger_on_rollback(self) -> None:
        logger = _make_logger()
        hub = ModelHub(version_logger=logger)
        hub.register_version(_backend("m"), "v1")
        hub.register_version(_backend("m"), "v2")
        hub.rollback("m", "v1")
        logger.on_rollback.assert_called_once()

    def test_rollback_logger_args(self) -> None:
        logger = _make_logger()
        hub = ModelHub(version_logger=logger)
        hub.register_version(_backend("m"), "v1")
        hub.register_version(_backend("m"), "v2")
        hub.rollback("m", "v1")
        args, _ = logger.on_rollback.call_args
        assert args[0] == "m"
        assert args[1] == "v2"   # from_version (was active before rollback)
        assert args[2] == "v1"   # to_version

    def test_rollback_no_logger_no_error(self) -> None:
        hub = ModelHub()
        hub.register_version(_backend("m"), "v1")
        hub.register_version(_backend("m"), "v2")
        assert hub.rollback("m", "v1") is True  # must not raise

    def test_rollback_failed_does_not_call_logger(self) -> None:
        logger = _make_logger()
        hub = ModelHub(version_logger=logger)
        hub.rollback("nonexistent", "v1")
        logger.on_rollback.assert_not_called()


# ---------------------------------------------------------------------------
# Backward compatibility: plain register() still works
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_register_unaffected_by_versioning(self) -> None:
        hub = ModelHub()
        b = _backend("plain")
        hub.register(b)
        assert hub.get("plain") is b
        assert hub.active_version("plain") is None

    def test_versioned_and_plain_coexist(self) -> None:
        hub = ModelHub()
        hub.register(_backend("plain"))
        hub.register_version(_backend("versioned"), "v1")
        assert hub.active_version("plain") is None
        assert hub.active_version("versioned") == "v1"
        assert len(hub) == 2
