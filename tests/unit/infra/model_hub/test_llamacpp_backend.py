"""Unit tests for LlamaCppBackend.

All tests run without a real llama-cpp-python installation.
The ``llama_cpp`` package is patched into sys.modules so that the
deferred import inside ``_get_model`` resolves to a mock.
"""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llama_cpp_module(text: str = "result") -> tuple[ModuleType, MagicMock]:
    """Return (fake_llama_cpp_module, mock_llama_instance).

    ``fake_llama_cpp_module.Llama(model_path=..., ...)`` returns
    ``mock_llama_instance``.  Calling ``mock_llama_instance(prompt, ...)``
    returns the llama.cpp completion dict format.
    """
    mock_instance = MagicMock(return_value={"choices": [{"text": text}]})
    fake_mod = ModuleType("llama_cpp")
    fake_mod.Llama = MagicMock(return_value=mock_instance)  # type: ignore[attr-defined]
    return fake_mod, mock_instance


# ---------------------------------------------------------------------------
# Module-level: no llama_cpp import
# ---------------------------------------------------------------------------


class TestLlamaCppModuleLevel:
    def test_module_importable_without_llama_cpp(self) -> None:
        saved = sys.modules.pop("llama_cpp", None)
        try:
            import importlib

            import llm_agents.infra.model_hub._llamacpp_backend as mod

            importlib.reload(mod)
        except ImportError:
            pytest.fail("Module import must not require llama_cpp")
        finally:
            if saved is not None:
                sys.modules["llama_cpp"] = saved

    def test_no_llama_cpp_top_level_import(self) -> None:
        import ast
        import inspect

        from llm_agents.infra.model_hub import _llamacpp_backend as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "llama_cpp":
                assert node.col_offset != 0, "llama_cpp must not be a top-level import"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "llama_cpp"

    def test_get_model_raises_import_error_when_missing(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        with patch.dict(sys.modules, {"llama_cpp": None}):  # type: ignore[dict-item]
            b = LlamaCppBackend("lc", "model.gguf")
            with pytest.raises(ImportError, match="llama-cpp-python"):
                b._get_model()


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestLlamaCppProtocol:
    def test_isinstance_model_backend(self) -> None:
        from llm_agents.infra.model_hub import ModelBackend
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("lc", "model.gguf")
        assert isinstance(b, ModelBackend)

    def test_generate_returns_str(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, _ = _make_llama_cpp_module("hi")
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b = LlamaCppBackend("lc", "model.gguf")
            result = asyncio.run(b.generate("prompt"))
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestLlamaCppInit:
    def test_name_stored(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("my-gguf", "model.gguf")
        assert b.name == "my-gguf"

    def test_model_path_stored(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("x", "/data/llama-2-7b.gguf")
        assert b._model_path == "/data/llama-2-7b.gguf"

    def test_default_n_ctx(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("x", "m.gguf")
        assert b._n_ctx == 2048

    def test_default_n_gpu_layers(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("x", "m.gguf")
        assert b._n_gpu_layers == 0

    def test_default_verbose(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("x", "m.gguf")
        assert b._verbose is False

    def test_default_max_tokens(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("x", "m.gguf")
        assert b._default_max_tokens == 256

    def test_default_temperature(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("x", "m.gguf")
        assert b._default_temperature == 0.0

    def test_model_none_at_init(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("x", "m.gguf")
        assert b._model is None

    def test_custom_n_ctx_and_gpu_layers(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("x", "m.gguf", n_ctx=4096, n_gpu_layers=32)
        assert b._n_ctx == 4096
        assert b._n_gpu_layers == 32


# ---------------------------------------------------------------------------
# _get_model
# ---------------------------------------------------------------------------


class TestLlamaCppGetModel:
    def test_model_loaded_lazily(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, _ = _make_llama_cpp_module()
        b = LlamaCppBackend("x", "m.gguf")
        assert b._model is None
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b._get_model()
        assert b._model is not None

    def test_model_cached_after_first_call(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, _ = _make_llama_cpp_module()
        b = LlamaCppBackend("x", "m.gguf")
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            m1 = b._get_model()
            m2 = b._get_model()
        assert m1 is m2
        fake_mod.Llama.assert_called_once()

    def test_llama_constructed_with_model_path(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, _ = _make_llama_cpp_module()
        b = LlamaCppBackend("x", "/models/llama.gguf")
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b._get_model()
        _, kwargs = fake_mod.Llama.call_args
        assert kwargs["model_path"] == "/models/llama.gguf"

    def test_llama_constructed_with_n_ctx(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, _ = _make_llama_cpp_module()
        b = LlamaCppBackend("x", "m.gguf", n_ctx=4096)
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b._get_model()
        _, kwargs = fake_mod.Llama.call_args
        assert kwargs["n_ctx"] == 4096

    def test_llama_constructed_with_n_gpu_layers(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, _ = _make_llama_cpp_module()
        b = LlamaCppBackend("x", "m.gguf", n_gpu_layers=32)
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b._get_model()
        _, kwargs = fake_mod.Llama.call_args
        assert kwargs["n_gpu_layers"] == 32


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


class TestLlamaCppGenerate:
    def test_returns_completion_text(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, _ = _make_llama_cpp_module("once upon a time")
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b = LlamaCppBackend("x", "m.gguf")
            result = asyncio.run(b.generate("tell me a story"))
        assert result == "once upon a time"

    def test_max_tokens_default(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, mock_inst = _make_llama_cpp_module()
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b = LlamaCppBackend("x", "m.gguf", max_tokens=128)
            asyncio.run(b.generate("p"))
        _, kwargs = mock_inst.call_args
        assert kwargs["max_tokens"] == 128

    def test_max_tokens_override(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, mock_inst = _make_llama_cpp_module()
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b = LlamaCppBackend("x", "m.gguf")
            asyncio.run(b.generate("p", max_tokens=32))
        _, kwargs = mock_inst.call_args
        assert kwargs["max_tokens"] == 32

    def test_temperature_default(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, mock_inst = _make_llama_cpp_module()
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b = LlamaCppBackend("x", "m.gguf", temperature=0.5)
            asyncio.run(b.generate("p"))
        _, kwargs = mock_inst.call_args
        assert kwargs["temperature"] == pytest.approx(0.5)

    def test_temperature_override(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, mock_inst = _make_llama_cpp_module()
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b = LlamaCppBackend("x", "m.gguf")
            asyncio.run(b.generate("p", temperature=0.9))
        _, kwargs = mock_inst.call_args
        assert kwargs["temperature"] == pytest.approx(0.9)

    def test_prompt_passed_to_model(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        fake_mod, mock_inst = _make_llama_cpp_module()
        with patch.dict(sys.modules, {"llama_cpp": fake_mod}):
            b = LlamaCppBackend("x", "m.gguf")
            asyncio.run(b.generate("my input"))
        args, _ = mock_inst.call_args
        assert args[0] == "my input"


# ---------------------------------------------------------------------------
# metadata()
# ---------------------------------------------------------------------------


class TestLlamaCppMetadata:
    def test_metadata_keys(self) -> None:
        from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend

        b = LlamaCppBackend("gguf-test", "/data/model.gguf", n_ctx=4096, n_gpu_layers=16)
        meta = b.metadata()
        assert meta["name"] == "gguf-test"
        assert meta["backend"] == "llamacpp"
        assert meta["model_path"] == "/data/model.gguf"
        assert meta["n_ctx"] == 4096
        assert meta["n_gpu_layers"] == 16
