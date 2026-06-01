"""Unit tests for NeMoGuard.

All tests run without a real nemoguardrails installation.
The ``nemoguardrails`` module is patched into sys.modules so that deferred
imports inside ``_get_rails`` resolve to mocks.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from llm_agents.infra.guardrails import Guard, GuardAction, GuardResult, NeMoGuard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_nemo_module(generate_response: str = "OK") -> tuple[ModuleType, MagicMock, MagicMock]:
    """Return (fake_nemoguardrails_module, mock_rails_instance, MockRailsConfig).

    ``fake_mod.LLMRails(config)`` returns ``mock_rails``.
    ``mock_rails.generate(messages=...)`` returns ``generate_response``.
    ``fake_mod.RailsConfig.from_path(path)`` returns a mock config object.
    """
    mock_rails = MagicMock()
    mock_rails.generate.return_value = generate_response

    mock_config = MagicMock()
    mock_RailsConfig = MagicMock()
    mock_RailsConfig.from_path = MagicMock(return_value=mock_config)

    fake_mod = ModuleType("nemoguardrails")
    fake_mod.LLMRails = MagicMock(return_value=mock_rails)  # type: ignore[attr-defined]
    fake_mod.RailsConfig = mock_RailsConfig  # type: ignore[attr-defined]

    return fake_mod, mock_rails, mock_RailsConfig


# ---------------------------------------------------------------------------
# Module-level: no nemoguardrails import at top
# ---------------------------------------------------------------------------


class TestNeMoGuardModuleLevel:
    def test_module_importable_without_nemoguardrails(self) -> None:
        saved = sys.modules.pop("nemoguardrails", None)
        try:
            import importlib

            import llm_agents.infra.guardrails._nemo_guard as mod

            importlib.reload(mod)
        except ImportError:
            pytest.fail("Module import must not require nemoguardrails")
        finally:
            if saved is not None:
                sys.modules["nemoguardrails"] = saved

    def test_no_nemoguardrails_top_level_import(self) -> None:
        import ast
        import inspect

        from llm_agents.infra.guardrails import _nemo_guard as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            is_nemo_from = isinstance(node, ast.ImportFrom) and (
                (node.module or "").startswith("nemoguardrails")
            )
            if is_nemo_from:
                assert node.col_offset != 0, "nemoguardrails must not be a top-level import"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "nemoguardrails" in alias.name:
                        assert node.col_offset != 0, "nemoguardrails must not be a top-level import"


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestNeMoGuardProtocol:
    def test_isinstance_guard(self) -> None:
        guard = NeMoGuard("/fake/path")
        assert isinstance(guard, Guard)

    def test_check_returns_guard_result(self) -> None:
        fake_mod, _, _ = _make_nemo_module("all good")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard = NeMoGuard("/fake/path", blocked_message_markers=[])
            result = guard.check("hello")
        assert isinstance(result, GuardResult)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestNeMoGuardInit:
    def test_config_path_stored(self) -> None:
        guard = NeMoGuard("/configs/nemo")
        assert guard._config_path == "/configs/nemo"

    def test_rails_none_at_init(self) -> None:
        guard = NeMoGuard("/configs/nemo")
        assert guard._rails is None

    def test_default_blocked_markers_used_when_none(self) -> None:
        guard = NeMoGuard("/configs/nemo")
        assert guard._blocked_markers == list(NeMoGuard.DEFAULT_BLOCKED_MARKERS)

    def test_custom_blocked_markers_stored(self) -> None:
        guard = NeMoGuard("/configs/nemo", blocked_message_markers=["NOPE", "DENIED"])
        assert "nope" in guard._blocked_markers
        assert "denied" in guard._blocked_markers

    def test_custom_markers_lowercased_at_init(self) -> None:
        guard = NeMoGuard("/configs/nemo", blocked_message_markers=["BLOCKED", "Sorry"])
        assert all(m == m.lower() for m in guard._blocked_markers)

    def test_empty_blocked_markers_stored(self) -> None:
        guard = NeMoGuard("/configs/nemo", blocked_message_markers=[])
        assert guard._blocked_markers == []

    def test_default_blocked_markers_nonempty(self) -> None:
        assert len(NeMoGuard.DEFAULT_BLOCKED_MARKERS) > 0


# ---------------------------------------------------------------------------
# _get_rails
# ---------------------------------------------------------------------------


class TestNeMoGuardGetRails:
    def test_raises_import_error_when_missing(self) -> None:
        with patch.dict(sys.modules, {"nemoguardrails": None}):  # type: ignore[dict-item]
            guard = NeMoGuard("/fake/path")
            with pytest.raises(ImportError, match="nemoguardrails"):
                guard._get_rails()

    def test_rails_loaded_lazily(self) -> None:
        fake_mod, _, _ = _make_nemo_module()
        guard = NeMoGuard("/fake/path")
        assert guard._rails is None
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard._get_rails()
        assert guard._rails is not None

    def test_rails_cached_after_first_call(self) -> None:
        fake_mod, _, _ = _make_nemo_module()
        guard = NeMoGuard("/fake/path")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            r1 = guard._get_rails()
            r2 = guard._get_rails()
        assert r1 is r2
        fake_mod.LLMRails.assert_called_once()

    def test_config_path_passed_to_from_path(self) -> None:
        fake_mod, _, MockRC = _make_nemo_module()
        guard = NeMoGuard("/my/nemo/config")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard._get_rails()
        MockRC.from_path.assert_called_once_with("/my/nemo/config")

    def test_llm_rails_constructed_with_config(self) -> None:
        fake_mod, _, MockRC = _make_nemo_module()
        guard = NeMoGuard("/my/config")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard._get_rails()
        config_obj = MockRC.from_path.return_value
        fake_mod.LLMRails.assert_called_once_with(config_obj)


# ---------------------------------------------------------------------------
# check()
# ---------------------------------------------------------------------------


class TestNeMoGuardCheck:
    def test_pass_when_response_has_no_marker(self) -> None:
        fake_mod, _, _ = _make_nemo_module("Here is the answer to your question.")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard = NeMoGuard("/cfg", blocked_message_markers=["i'm sorry"])
            result = guard.check("what is 2+2?")
        assert result.passed is True
        assert result.action == GuardAction.PASS

    def test_block_when_response_contains_marker(self) -> None:
        fake_mod, _, _ = _make_nemo_module("I'm sorry, I can't help with that.")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard = NeMoGuard("/cfg", blocked_message_markers=["i'm sorry"])
            result = guard.check("harmful request")
        assert result.passed is False
        assert result.action == GuardAction.BLOCK

    def test_block_detail_contains_response(self) -> None:
        response = "I cannot assist with that request."
        fake_mod, _, _ = _make_nemo_module(response)
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard = NeMoGuard("/cfg", blocked_message_markers=["i cannot assist"])
            result = guard.check("bad input")
        assert response in (result.violation_detail or "")

    def test_marker_match_is_case_insensitive(self) -> None:
        # Response is uppercase, marker is lowercase
        fake_mod, _, _ = _make_nemo_module("I'M SORRY, I CAN'T HELP WITH THAT.")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard = NeMoGuard("/cfg", blocked_message_markers=["i'm sorry"])
            result = guard.check("bad input")
        assert result.passed is False

    def test_empty_markers_always_passes(self) -> None:
        fake_mod, _, _ = _make_nemo_module("I'm sorry, cannot do that at all.")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard = NeMoGuard("/cfg", blocked_message_markers=[])
            result = guard.check("anything")
        assert result.passed is True

    def test_prompt_passed_as_user_message(self) -> None:
        fake_mod, mock_rails, _ = _make_nemo_module("OK")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard = NeMoGuard("/cfg", blocked_message_markers=[])
            guard.check("my specific prompt")
        args, kwargs = mock_rails.generate.call_args
        messages = kwargs.get("messages", args[0] if args else None)
        assert messages is not None
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "my specific prompt"

    def test_multiple_markers_first_matching_triggers_block(self) -> None:
        fake_mod, _, _ = _make_nemo_module("I cannot help with that topic.")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard = NeMoGuard("/cfg", blocked_message_markers=["will not match", "i cannot help"])
            result = guard.check("bad input")
        assert result.passed is False

    def test_original_text_preserved_in_block_result(self) -> None:
        fake_mod, _, _ = _make_nemo_module("I'm sorry, I can't help.")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard = NeMoGuard("/cfg", blocked_message_markers=["i'm sorry"])
            result = guard.check("original input text")
        assert result.text == "original input text"

    def test_pass_text_unchanged(self) -> None:
        fake_mod, _, _ = _make_nemo_module("Sure, here is the answer.")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            guard = NeMoGuard("/cfg", blocked_message_markers=["i'm sorry"])
            result = guard.check("benign question")
        assert result.text == "benign question"

    def test_each_default_marker_triggers_block(self) -> None:
        """Each DEFAULT_BLOCKED_MARKERS entry must trigger BLOCK."""
        for marker in NeMoGuard.DEFAULT_BLOCKED_MARKERS:
            fake_mod, _, _ = _make_nemo_module(f"Response: {marker} some extra text.")
            with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
                guard = NeMoGuard("/cfg")
                result = guard.check("request")
            assert result.passed is False, f"Marker {marker!r} did not trigger BLOCK"

    def test_nemo_guard_composable_in_chain(self) -> None:
        from llm_agents.infra.guardrails import GuardrailChain, KeywordFilter

        fake_mod, _, _ = _make_nemo_module("I'm sorry, I cannot help.")
        with patch.dict(sys.modules, {"nemoguardrails": fake_mod}):
            chain = GuardrailChain(
                [
                    KeywordFilter(["explicit_keyword"]),
                    NeMoGuard("/cfg", blocked_message_markers=["i'm sorry"]),
                ]
            )
            result = chain.run("a harmful request")
        assert result.passed is False
        assert result.action == GuardAction.BLOCK
