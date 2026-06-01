"""Unit tests for HuggingFaceBackend.

All tests run without a real transformers installation.
The ``transformers`` package is patched into sys.modules so that the
deferred import inside ``_get_pipeline`` resolves to a mock.
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


def _make_pipeline_result(text: str = "hello") -> list[dict]:
    """Return a mock transformers pipeline output."""
    return [{"generated_text": text}]


def _make_transformers_module(text: str = "hello") -> tuple[ModuleType, MagicMock]:
    """Return (fake_transformers_module, mock_pipe_callable).

    ``fake_transformers_module.pipeline("text-generation", model=..., ...)``
    returns ``mock_pipe_callable``.  Calling ``mock_pipe_callable(prompt, ...)``
    returns ``[{"generated_text": text}]``.
    """
    mock_pipe = MagicMock(return_value=_make_pipeline_result(text))
    fake_mod = ModuleType("transformers")
    fake_mod.pipeline = MagicMock(return_value=mock_pipe)  # type: ignore[attr-defined]
    return fake_mod, mock_pipe


# ---------------------------------------------------------------------------
# Module-level: no transformers import
# ---------------------------------------------------------------------------


class TestHFModuleLevel:
    def test_module_importable_without_transformers(self) -> None:
        saved = sys.modules.pop("transformers", None)
        try:
            import importlib

            import llm_agents.infra.model_hub._huggingface_backend as mod

            importlib.reload(mod)
        except ImportError:
            pytest.fail("Module import must not require transformers")
        finally:
            if saved is not None:
                sys.modules["transformers"] = saved

    def test_no_transformers_top_level_import(self) -> None:
        import ast
        import inspect

        from llm_agents.infra.model_hub import _huggingface_backend as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "transformers":
                assert node.col_offset != 0, "transformers must not be a top-level import"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "transformers"

    def test_get_pipeline_raises_import_error_when_missing(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        with patch.dict(sys.modules, {"transformers": None}):  # type: ignore[dict-item]
            b = HuggingFaceBackend("hf", "gpt2")
            with pytest.raises(ImportError, match="transformers"):
                b._get_pipeline()


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestHFProtocol:
    def test_isinstance_model_backend(self) -> None:
        from llm_agents.infra.model_hub import ModelBackend
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        b = HuggingFaceBackend("hf", "gpt2")
        assert isinstance(b, ModelBackend)

    def test_generate_returns_str(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, _ = _make_transformers_module("world")
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b = HuggingFaceBackend("hf", "gpt2")
            result = asyncio.run(b.generate("hi"))
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestHFInit:
    def test_name_stored(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        b = HuggingFaceBackend("my-hf", "gpt2")
        assert b.name == "my-hf"

    def test_model_id_stored(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        b = HuggingFaceBackend("x", "mistralai/Mistral-7B-v0.1")
        assert b._model_id == "mistralai/Mistral-7B-v0.1"

    def test_default_device(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        b = HuggingFaceBackend("x", "gpt2")
        assert b._device == "cpu"

    def test_custom_device(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        b = HuggingFaceBackend("x", "gpt2", device="cuda")
        assert b._device == "cuda"

    def test_default_max_tokens(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        b = HuggingFaceBackend("x", "gpt2")
        assert b._default_max_tokens == 256

    def test_default_temperature(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        b = HuggingFaceBackend("x", "gpt2")
        assert b._default_temperature == 0.0

    def test_pipeline_none_at_init(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        b = HuggingFaceBackend("x", "gpt2")
        assert b._pipeline is None


# ---------------------------------------------------------------------------
# _get_pipeline
# ---------------------------------------------------------------------------


class TestHFGetPipeline:
    def test_pipeline_loaded_lazily(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, _ = _make_transformers_module()
        b = HuggingFaceBackend("x", "gpt2")
        assert b._pipeline is None
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b._get_pipeline()
        assert b._pipeline is not None

    def test_pipeline_cached_after_first_call(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, _ = _make_transformers_module()
        b = HuggingFaceBackend("x", "gpt2")
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            p1 = b._get_pipeline()
            p2 = b._get_pipeline()
        assert p1 is p2
        fake_mod.pipeline.assert_called_once()

    def test_pipeline_constructed_with_model_id(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, _ = _make_transformers_module()
        b = HuggingFaceBackend("x", "gpt2")
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b._get_pipeline()
        _, kwargs = fake_mod.pipeline.call_args
        assert kwargs["model"] == "gpt2"

    def test_pipeline_constructed_with_device(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, _ = _make_transformers_module()
        b = HuggingFaceBackend("x", "gpt2", device="cuda")
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b._get_pipeline()
        _, kwargs = fake_mod.pipeline.call_args
        assert kwargs["device"] == "cuda"

    def test_pipeline_task_is_text_generation(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, _ = _make_transformers_module()
        b = HuggingFaceBackend("x", "gpt2")
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b._get_pipeline()
        args, _ = fake_mod.pipeline.call_args
        assert args[0] == "text-generation"

    def test_torch_dtype_forwarded_when_set(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, _ = _make_transformers_module()
        sentinel = object()
        b = HuggingFaceBackend("x", "gpt2", torch_dtype=sentinel)
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b._get_pipeline()
        _, kwargs = fake_mod.pipeline.call_args
        assert kwargs["torch_dtype"] is sentinel

    def test_torch_dtype_absent_when_none(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, _ = _make_transformers_module()
        b = HuggingFaceBackend("x", "gpt2")
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b._get_pipeline()
        _, kwargs = fake_mod.pipeline.call_args
        assert "torch_dtype" not in kwargs


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


class TestHFGenerate:
    def test_returns_generated_text(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, _ = _make_transformers_module("the answer is 42")
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b = HuggingFaceBackend("x", "gpt2")
            result = asyncio.run(b.generate("question?"))
        assert result == "the answer is 42"

    def test_max_new_tokens_default(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, mock_pipe = _make_transformers_module()
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b = HuggingFaceBackend("x", "gpt2", max_tokens=128)
            asyncio.run(b.generate("p"))
        _, kwargs = mock_pipe.call_args
        assert kwargs["max_new_tokens"] == 128

    def test_max_tokens_override(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, mock_pipe = _make_transformers_module()
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b = HuggingFaceBackend("x", "gpt2")
            asyncio.run(b.generate("p", max_tokens=64))
        _, kwargs = mock_pipe.call_args
        assert kwargs["max_new_tokens"] == 64

    def test_do_sample_false_when_temperature_zero(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, mock_pipe = _make_transformers_module()
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b = HuggingFaceBackend("x", "gpt2", temperature=0.0)
            asyncio.run(b.generate("p"))
        _, kwargs = mock_pipe.call_args
        assert kwargs["do_sample"] is False

    def test_do_sample_true_when_temperature_positive(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, mock_pipe = _make_transformers_module()
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b = HuggingFaceBackend("x", "gpt2", temperature=0.7)
            asyncio.run(b.generate("p"))
        _, kwargs = mock_pipe.call_args
        assert kwargs["do_sample"] is True
        assert kwargs["temperature"] == pytest.approx(0.7)

    def test_temperature_not_in_kwargs_when_zero(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, mock_pipe = _make_transformers_module()
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b = HuggingFaceBackend("x", "gpt2", temperature=0.0)
            asyncio.run(b.generate("p"))
        _, kwargs = mock_pipe.call_args
        assert "temperature" not in kwargs

    def test_return_full_text_false(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, mock_pipe = _make_transformers_module()
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b = HuggingFaceBackend("x", "gpt2")
            asyncio.run(b.generate("p"))
        _, kwargs = mock_pipe.call_args
        assert kwargs["return_full_text"] is False

    def test_prompt_passed_to_pipeline(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        fake_mod, mock_pipe = _make_transformers_module()
        with patch.dict(sys.modules, {"transformers": fake_mod}):
            b = HuggingFaceBackend("x", "gpt2")
            asyncio.run(b.generate("my prompt"))
        args, _ = mock_pipe.call_args
        assert args[0] == "my prompt"


# ---------------------------------------------------------------------------
# metadata()
# ---------------------------------------------------------------------------


class TestHFMetadata:
    def test_metadata_keys(self) -> None:
        from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend

        b = HuggingFaceBackend("hf-test", "gpt2", device="cuda")
        meta = b.metadata()
        assert meta["name"] == "hf-test"
        assert meta["backend"] == "huggingface"
        assert meta["model_id"] == "gpt2"
        assert meta["device"] == "cuda"
