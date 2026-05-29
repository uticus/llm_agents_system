"""Provider protocol and FakeProvider for the inference-routing subsystem.

``Provider`` is a :class:`typing.Protocol` (structural subtyping) — adapters
implement the interface without inheriting from it.

``FakeProvider`` is the in-memory test double; it never makes network calls.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from llm_agents.infra.inference_routing._models import LLMRequest, LLMResponse


@runtime_checkable
class Provider(Protocol):
    """Async LLM adapter interface.

    Any class with a ``name: str`` attribute and a matching ``complete``
    coroutine method satisfies this protocol without explicit inheritance.
    """

    name: str

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send *request* to the LLM and return a :class:`LLMResponse`.

        Raises:
            Exception: Any provider-level error (rate limit, network, etc.).
        """
        ...


class FakeProvider:
    """In-memory provider for tests.

    Plays back a pre-configured sequence of :class:`LLMResponse` objects or
    exceptions.  When the sequence is exhausted, the last item is repeated
    indefinitely.

    Args:
        name:      Provider name (appears in span attributes).
        responses: Ordered list of responses or exceptions to return.
                   An :class:`Exception` instance is raised rather than returned.
    """

    def __init__(
        self,
        name: str,
        responses: list[LLMResponse | BaseException],
    ) -> None:
        if not responses:
            raise ValueError("FakeProvider requires at least one response or exception")
        self.name = name
        self._responses: list[LLMResponse | BaseException] = list(responses)
        self._index: int = 0
        self.call_count: int = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return or raise the next item in the pre-configured sequence."""
        idx = min(self._index, len(self._responses) - 1)
        item = self._responses[idx]
        self._index += 1
        self.call_count += 1
        if isinstance(item, BaseException):
            raise item
        return item
