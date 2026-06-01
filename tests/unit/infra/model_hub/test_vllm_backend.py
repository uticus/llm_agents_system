"""Unit tests for VLLMBackend.

All tests run without a real vllm installation.
The ``vllm`` package is patched into sys.modules so that the deferred
imports inside ``_get_llm`` and ``generate`` resolve to mocks.
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


def _make_vllm_module(text: str = "result") -> tuple[ModuleType, MagicMock, MagicMock]:
    """Return (fake_vllm_module, mock_llm_instance, mock_SamplingParams_class).

    ``fake_vllm_module.LLM(model=..., ...)`` returns ``mock_llm_instance``.
    ``mock_llm_instance.generate([prompt], sampling_params)`` returns a list
    resembling vLLM's RequestOutput objects.
    ``fake_vllm_module.SamplingParams(...)`` returns a mock sampling-params obj.
    """
    # Build a mock output resembling vllm.outputs.RequestOutput
    mock_output_text = MagicMock()
    mock_output_text.text = text
    mock_request_output = MagicMock()
    mock_request_output.outputs = [mock_output_text]

    mock_llm = MagicMock()
    mock_llm.generate.return_value = [mock_request_output]

    mock_sampling_params = MagicMock()

    fake_mod = ModuleType("vllm")
    fake_mod.LLM = MagicMock(return_value=mock_llm)  # type: ignore[attr-defined]
    fake_mod.SamplingParams = MagicMock(return_value=mock_sampling_params)  # type: ignore[attr-defined]

    return fake_mod, mock_llm, fake_mod.SamplingParams


# ---------------------------------------------------------------------------
# Module-level: no vllm import
# ---------------------------------------------------------------------------


class TestVLLMModuleLevel:
    def test_module_importable_without_vllm(self) -> None:
        saved = sys.modules.pop("vllm", None)
        try:
            import importlib

            import llm_agents.infra.model_hub._vllm_backend as mod

            importlib.reload(mod)
        except ImportError:
            pytest.fail("Module import must not require vllm")
        finally:
            if saved is not None:
                sys.modules["vllm"] = saved

    def test_no_vllm_top_level_import(self) -> None:
        import ast
        import inspect

        from llm_agents.infra.model_hub import _vllm_backend as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "vllm":
                assert node.col_offset != 0, "vllm must not be a top-level import"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "vllm"

    def test_get_llm_raises_import_error_when_missing(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        with patch.dict(sys.modules, {"vllm": None}):  # type: ignore[dict-item]
            b = VLLMBackend("vllm", "meta-llama/Llama-2-7b")
            with pytest.raises(ImportError, match="vllm"):
                b._get_llm()


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestVLLMProtocol:
    def test_isinstance_model_backend(self) -> None:
        from llm_agents.infra.model_hub import ModelBackend
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        b = VLLMBackend("v", "llama")
        assert isinstance(b, ModelBackend)

    def test_generate_returns_str(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, _, _ = _make_vllm_module("hello")
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            b = VLLMBackend("v", "llama")
            result = asyncio.run(b.generate("p"))
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestVLLMInit:
    def test_name_stored(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        b = VLLMBackend("my-vllm", "llama")
        assert b.name == "my-vllm"

    def test_model_id_stored(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        b = VLLMBackend("x", "meta-llama/Llama-2-7b-hf")
        assert b._model_id == "meta-llama/Llama-2-7b-hf"

    def test_default_gpu_memory_utilization(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        b = VLLMBackend("x", "llama")
        assert b._gpu_memory_utilization == pytest.approx(0.9)

    def test_default_max_tokens(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        b = VLLMBackend("x", "llama")
        assert b._default_max_tokens == 256

    def test_default_temperature(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        b = VLLMBackend("x", "llama")
        assert b._default_temperature == 0.0

    def test_llm_none_at_init(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        b = VLLMBackend("x", "llama")
        assert b._llm is None

    def test_custom_gpu_memory_utilization(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        b = VLLMBackend("x", "llama", gpu_memory_utilization=0.7)
        assert b._gpu_memory_utilization == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# _get_llm
# ---------------------------------------------------------------------------


class TestVLLMGetLLM:
    def test_llm_loaded_lazily(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, _, _ = _make_vllm_module()
        b = VLLMBackend("x", "llama")
        assert b._llm is None
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            b._get_llm()
        assert b._llm is not None

    def test_llm_cached_after_first_call(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, _, _ = _make_vllm_module()
        b = VLLMBackend("x", "llama")
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            l1 = b._get_llm()
            l2 = b._get_llm()
        assert l1 is l2
        fake_mod.LLM.assert_called_once()

    def test_llm_constructed_with_model_id(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, _, _ = _make_vllm_module()
        b = VLLMBackend("x", "meta-llama/Llama-2-7b-hf")
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            b._get_llm()
        _, kwargs = fake_mod.LLM.call_args
        assert kwargs["model"] == "meta-llama/Llama-2-7b-hf"

    def test_llm_constructed_with_gpu_memory_utilization(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, _, _ = _make_vllm_module()
        b = VLLMBackend("x", "llama", gpu_memory_utilization=0.8)
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            b._get_llm()
        _, kwargs = fake_mod.LLM.call_args
        assert kwargs["gpu_memory_utilization"] == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


class TestVLLMGenerate:
    def test_returns_generated_text(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, _, _ = _make_vllm_module("the capital is Paris")
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            b = VLLMBackend("x", "llama")
            result = asyncio.run(b.generate("what is the capital?"))
        assert result == "the capital is Paris"

    def test_sampling_params_max_tokens(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, _, MockSP = _make_vllm_module()
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            b = VLLMBackend("x", "llama", max_tokens=64)
            asyncio.run(b.generate("p"))
        _, kwargs = MockSP.call_args
        assert kwargs["max_tokens"] == 64

    def test_sampling_params_temperature(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, _, MockSP = _make_vllm_module()
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            b = VLLMBackend("x", "llama", temperature=0.8)
            asyncio.run(b.generate("p"))
        _, kwargs = MockSP.call_args
        assert kwargs["temperature"] == pytest.approx(0.8)

    def test_max_tokens_override(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, _, MockSP = _make_vllm_module()
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            b = VLLMBackend("x", "llama")
            asyncio.run(b.generate("p", max_tokens=16))
        _, kwargs = MockSP.call_args
        assert kwargs["max_tokens"] == 16

    def test_temperature_override(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, _, MockSP = _make_vllm_module()
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            b = VLLMBackend("x", "llama")
            asyncio.run(b.generate("p", temperature=0.3))
        _, kwargs = MockSP.call_args
        assert kwargs["temperature"] == pytest.approx(0.3)

    def test_prompt_passed_to_llm_generate(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        fake_mod, mock_llm, _ = _make_vllm_module()
        with patch.dict(sys.modules, {"vllm": fake_mod}):
            b = VLLMBackend("x", "llama")
            asyncio.run(b.generate("my specific prompt"))
        args, _ = mock_llm.generate.call_args
        assert args[0] == ["my specific prompt"]


# ---------------------------------------------------------------------------
# metadata()
# ---------------------------------------------------------------------------


class TestVLLMMetadata:
    def test_metadata_keys(self) -> None:
        from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

        b = VLLMBackend("vllm-test", "meta-llama/Llama-2-7b", gpu_memory_utilization=0.8)
        meta = b.metadata()
        assert meta["name"] == "vllm-test"
        assert meta["backend"] == "vllm"
        assert meta["model_id"] == "meta-llama/Llama-2-7b"
        assert meta["gpu_memory_utilization"] == pytest.approx(0.8)
