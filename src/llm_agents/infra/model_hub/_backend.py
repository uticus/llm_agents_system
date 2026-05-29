"""ModelBackend protocol and FakeBackend implementation.

:class:`ModelBackend` is a structural ``Protocol`` — any class with matching
``name``, ``generate``, and ``metadata`` members qualifies without inheriting.

:class:`FakeBackend` is a deterministic test stub that cycles through a list
of preset response strings.
"""

from __future__ import annotations

from typing import Any

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable


@runtime_checkable
class ModelBackend(Protocol):
    """Protocol for model backends.

    Any object with matching ``name``, ``generate``, and ``metadata`` members
    satisfies this interface without needing to inherit from
    :class:`ModelBackend`.
    """

    name: str

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        """Generate text from *prompt*.

        Args:
            prompt:      Input text.
            max_tokens:  Maximum tokens to generate.
            temperature: Sampling temperature (0.0 = deterministic).

        Returns:
            Generated text string.
        """
        ...

    def metadata(self) -> dict[str, Any]:
        """Return backend metadata (model name, capabilities, cost, etc.)."""
        ...


class FakeBackend:
    """Deterministic test backend that cycles through preset responses.

    Args:
        name:      Backend name identifier.
        responses: Ordered list of strings to return from :meth:`generate`.
                   Cycles when exhausted.
    """

    def __init__(self, name: str, responses: list[str]) -> None:
        if not responses:
            raise ValueError("FakeBackend requires at least one response.")
        self.name = name
        self._responses = list(responses)
        self._index = 0
        self.call_count = 0

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        """Return the next preset response (cycling)."""
        response = self._responses[self._index % len(self._responses)]
        self._index += 1
        self.call_count += 1
        return response

    def metadata(self) -> dict[str, Any]:
        """Return stub metadata."""
        return {
            "name": self.name,
            "backend": "fake",
            "max_tokens": 256,
        }
