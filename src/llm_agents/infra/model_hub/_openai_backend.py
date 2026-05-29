"""OpenAI backend stub.

:class:`OpenAIBackend` is a thin wrapper around the ``openai`` package.
The import is deferred to :meth:`generate` so that importing this module
without ``openai`` installed does not raise an :class:`ImportError`.

To use this backend, install the optional ``openai`` extra::

    pip install llm-agents[openai]
"""

from __future__ import annotations

from typing import Any


class OpenAIBackend:
    """ModelBackend adapter for the OpenAI Chat Completions API.

    The ``openai`` package must be installed to call :meth:`generate`.
    Importing this class does not require ``openai`` to be present.

    Args:
        name:        Logical backend name (e.g. ``"gpt-4o"``).
        model_id:    OpenAI model identifier (e.g. ``"gpt-4o"``).
        api_key:     OpenAI API key.  Defaults to the ``OPENAI_API_KEY``
                     environment variable when ``None``.
        max_tokens:  Default max tokens for generate calls.
        temperature: Default sampling temperature.
    """

    def __init__(
        self,
        name: str,
        model_id: str = "gpt-4o",
        api_key: str | None = None,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None:
        self.name = name
        self._model_id = model_id
        self._api_key = api_key
        self._default_max_tokens = max_tokens
        self._default_temperature = temperature

    async def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Call the OpenAI Chat Completions API and return the text response.

        Raises:
            ImportError: If the ``openai`` package is not installed.
        """
        try:
            import openai  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required for OpenAIBackend. "
                "Install it with: pip install llm-agents[openai]"
            ) from exc

        client = openai.AsyncOpenAI(api_key=self._api_key)
        response = await client.chat.completions.create(
            model=self._model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens or self._default_max_tokens,
            temperature=temperature if temperature is not None else self._default_temperature,
        )
        return response.choices[0].message.content or ""

    def metadata(self) -> dict[str, Any]:
        """Return backend metadata."""
        return {
            "name": self.name,
            "backend": "openai",
            "model_id": self._model_id,
        }
