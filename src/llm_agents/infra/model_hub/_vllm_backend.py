"""VLLMBackend: text generation via vLLM (LLM inference server).

Requires the ``local-inference`` optional extra (``vllm`` package, Linux only).
The import is deferred to :meth:`_get_llm` and :meth:`generate` so that
importing this module without the extra installed does not raise.
"""

from __future__ import annotations

from typing import Any


class VLLMBackend:
    """ModelBackend adapter backed by ``vllm.LLM`` for high-throughput local inference.

    The vLLM engine is loaded lazily on the first :meth:`generate` call.
    Inference is dispatched to the default thread-pool executor because
    ``vllm.LLM.generate`` is synchronous.

    vLLM requires a Linux host with a CUDA GPU.  Import this backend only on
    Linux; the ``local-inference`` extra excludes it on other platforms.

    Args:
        name:                  Logical backend name used by :class:`ModelHub`.
        model_id:              Hugging Face model identifier or local path.
        gpu_memory_utilization: Fraction of GPU memory to reserve for the model
                               weights and KV cache.  Defaults to ``0.9``.
        max_tokens:            Default token budget for :meth:`generate` calls.
        temperature:           Default sampling temperature.  ``0.0`` (default)
                               uses greedy decoding.

    Attributes:
        name: Logical backend name.
    """

    def __init__(
        self,
        name: str,
        model_id: str,
        *,
        gpu_memory_utilization: float = 0.9,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None:
        self.name = name
        self._model_id = model_id
        self._gpu_memory_utilization = gpu_memory_utilization
        self._default_max_tokens = max_tokens
        self._default_temperature = temperature
        self._llm = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_llm(self):
        """Return the loaded ``vllm.LLM`` engine instance.

        Raises:
            ImportError: If ``vllm`` is not installed.
        """
        if self._llm is None:
            try:
                from vllm import LLM  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "vllm is required for VLLMBackend. "
                    "Install it with: pip install 'llm-agents-system[local-inference]' "
                    "(Linux with CUDA only)"
                ) from exc
            self._llm = LLM(
                model=self._model_id,
                gpu_memory_utilization=self._gpu_memory_utilization,
            )
        return self._llm

    # ------------------------------------------------------------------
    # ModelBackend protocol
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Run text generation via the vLLM engine.

        The engine is loaded on the first call.  Inference is run in the
        default thread-pool executor to avoid blocking the event loop.

        Args:
            prompt:      Input text.
            max_tokens:  Maximum tokens to generate.  Defaults to the value
                         set at construction.
            temperature: Sampling temperature.  Defaults to the value set
                         at construction.

        Returns:
            Generated text string.

        Raises:
            ImportError: If ``vllm`` is not installed.
        """
        import asyncio

        try:
            from vllm import SamplingParams  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "vllm is required for VLLMBackend. "
                "Install it with: pip install 'llm-agents-system[local-inference]' "
                "(Linux with CUDA only)"
            ) from exc

        llm = self._get_llm()
        _max_tokens = max_tokens if max_tokens is not None else self._default_max_tokens
        _temperature = temperature if temperature is not None else self._default_temperature
        sampling_params = SamplingParams(max_tokens=_max_tokens, temperature=_temperature)

        loop = asyncio.get_event_loop()
        outputs = await loop.run_in_executor(
            None,
            lambda: llm.generate([prompt], sampling_params),
        )
        return outputs[0].outputs[0].text

    def metadata(self) -> dict[str, Any]:
        """Return backend metadata."""
        return {
            "name": self.name,
            "backend": "vllm",
            "model_id": self._model_id,
            "gpu_memory_utilization": self._gpu_memory_utilization,
        }
