"""LlamaCppBackend: text generation via llama-cpp-python (GGUF models).

Requires the ``local-inference`` optional extra (``llama-cpp-python`` package).
The import is deferred to :meth:`_get_model` so that importing this module
without the extra installed does not raise.
"""

from __future__ import annotations

from typing import Any


class LlamaCppBackend:
    """ModelBackend adapter backed by a GGUF model loaded via ``llama_cpp.Llama``.

    The model is loaded lazily on the first :meth:`generate` call, so
    ``import llama_cpp`` is deferred until the model is actually needed.
    Inference is dispatched to the default thread-pool executor so the async
    interface does not block the event loop.

    Args:
        name:          Logical backend name used by :class:`ModelHub`.
        model_path:    Path to the GGUF model file on disk.
        n_ctx:         Context window size in tokens.  Defaults to ``2048``.
        n_gpu_layers:  Number of model layers to offload to GPU.
                       ``0`` (default) runs entirely on CPU.
        verbose:       If ``True``, llama.cpp prints progress to stdout.
                       Defaults to ``False``.
        max_tokens:    Default token budget for :meth:`generate` calls.
        temperature:   Default sampling temperature.  ``0.0`` (default) uses
                       greedy decoding.

    Attributes:
        name:       Logical backend name.
    """

    def __init__(
        self,
        name: str,
        model_path: str,
        *,
        n_ctx: int = 2048,
        n_gpu_layers: int = 0,
        verbose: bool = False,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None:
        self.name = name
        self._model_path = model_path
        self._n_ctx = n_ctx
        self._n_gpu_layers = n_gpu_layers
        self._verbose = verbose
        self._default_max_tokens = max_tokens
        self._default_temperature = temperature
        self._model = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_model(self):
        """Return the loaded ``llama_cpp.Llama`` model instance.

        Raises:
            ImportError: If ``llama-cpp-python`` is not installed.
        """
        if self._model is None:
            try:
                from llama_cpp import Llama  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "llama-cpp-python is required for LlamaCppBackend. "
                    "Install it with: pip install 'llm-agents-system[local-inference]'"
                ) from exc
            self._model = Llama(
                model_path=self._model_path,
                n_ctx=self._n_ctx,
                n_gpu_layers=self._n_gpu_layers,
                verbose=self._verbose,
            )
        return self._model

    # ------------------------------------------------------------------
    # ModelBackend protocol
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Run text completion via the llama.cpp GGUF model.

        The model is loaded on the first call.  Inference is run in the
        default thread-pool executor to avoid blocking the event loop.

        Args:
            prompt:      Input text.
            max_tokens:  Maximum tokens to generate.  Defaults to the value
                         set at construction.
            temperature: Sampling temperature.  Defaults to the value set
                         at construction.

        Returns:
            Generated completion text.

        Raises:
            ImportError: If ``llama-cpp-python`` is not installed.
        """
        import asyncio

        model = self._get_model()
        _max_tokens = max_tokens if max_tokens is not None else self._default_max_tokens
        _temperature = temperature if temperature is not None else self._default_temperature

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model(prompt, max_tokens=_max_tokens, temperature=_temperature),
        )
        return result["choices"][0]["text"]

    def metadata(self) -> dict[str, Any]:
        """Return backend metadata."""
        return {
            "name": self.name,
            "backend": "llamacpp",
            "model_path": self._model_path,
            "n_ctx": self._n_ctx,
            "n_gpu_layers": self._n_gpu_layers,
        }
