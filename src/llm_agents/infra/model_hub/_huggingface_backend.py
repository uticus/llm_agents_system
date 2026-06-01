"""HuggingFaceBackend: text generation via transformers.pipeline.

Requires the ``training`` optional extra (``transformers`` package).
The import is deferred to :meth:`_get_pipeline` so that importing this
module without the extra installed does not raise.
"""

from __future__ import annotations

from typing import Any


class HuggingFaceBackend:
    """ModelBackend adapter backed by a Hugging Face ``text-generation`` pipeline.

    The pipeline is loaded lazily on the first :meth:`generate` call, so
    ``import transformers`` is deferred until the model is actually needed.
    Inference is dispatched to the default thread-pool executor so the async
    interface does not block the event loop.

    Args:
        name:        Logical backend name used by :class:`ModelHub`.
        model_id:    Hugging Face model identifier or local path
                     (e.g. ``"gpt2"``, ``"mistralai/Mistral-7B-v0.1"``).
        device:      Torch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
                     Defaults to ``"cpu"``.
        torch_dtype: Optional ``torch.dtype`` forwarded to the pipeline
                     constructor (e.g. ``torch.float16`` for half-precision).
                     ``None`` (default) leaves the dtype at the library default.
        max_tokens:  Default ``max_new_tokens`` for :meth:`generate` calls.
        temperature: Default sampling temperature.  ``0.0`` (default) uses
                     greedy decoding.

    Attributes:
        name:      Logical backend name.
    """

    def __init__(
        self,
        name: str,
        model_id: str,
        *,
        device: str = "cpu",
        torch_dtype: Any = None,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None:
        self.name = name
        self._model_id = model_id
        self._device = device
        self._torch_dtype = torch_dtype
        self._default_max_tokens = max_tokens
        self._default_temperature = temperature
        self._pipeline = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_pipeline(self):
        """Return the loaded ``transformers`` text-generation pipeline.

        Raises:
            ImportError: If ``transformers`` is not installed.
        """
        if self._pipeline is None:
            try:
                from transformers import pipeline  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "transformers is required for HuggingFaceBackend. "
                    "Install it with: pip install 'llm-agents-system[training]'"
                ) from exc
            kwargs: dict[str, Any] = {"device": self._device}
            if self._torch_dtype is not None:
                kwargs["torch_dtype"] = self._torch_dtype
            self._pipeline = pipeline("text-generation", model=self._model_id, **kwargs)
        return self._pipeline

    # ------------------------------------------------------------------
    # ModelBackend protocol
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Run text generation via the HuggingFace pipeline.

        The pipeline is loaded on the first call.  Inference is run in the
        default thread-pool executor to avoid blocking the event loop.

        Args:
            prompt:      Input text.
            max_tokens:  Maximum new tokens to generate.  Defaults to the
                         value set at construction.
            temperature: Sampling temperature.  ``0.0`` uses greedy decoding.
                         Defaults to the value set at construction.

        Returns:
            Newly generated text (prompt not included).

        Raises:
            ImportError: If ``transformers`` is not installed.
        """
        import asyncio

        pipe = self._get_pipeline()
        _max_tokens = max_tokens if max_tokens is not None else self._default_max_tokens
        _temperature = temperature if temperature is not None else self._default_temperature
        call_kwargs: dict[str, Any] = {
            "max_new_tokens": _max_tokens,
            "do_sample": _temperature > 0.0,
            "return_full_text": False,
        }
        if _temperature > 0.0:
            call_kwargs["temperature"] = _temperature

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: pipe(prompt, **call_kwargs))
        return result[0]["generated_text"]

    def metadata(self) -> dict[str, Any]:
        """Return backend metadata."""
        return {
            "name": self.name,
            "backend": "huggingface",
            "model_id": self._model_id,
            "device": self._device,
        }
