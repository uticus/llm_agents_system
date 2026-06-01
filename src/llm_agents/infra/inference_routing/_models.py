"""Data model for the inference-routing subsystem.

All types are pure data — no I/O, no async, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llm_agents.infra.inference_routing._provider import Provider


@dataclass
class LLMRequest:
    """Uniform request sent to any LLM provider.

    Args:
        model:       Target model identifier (e.g. ``"gpt-4o"``).
        messages:    Chat messages in OpenAI format — ``[{"role": "user",
                     "content": "..."}]``.
        max_tokens:  Maximum tokens the model may generate.
        temperature: Sampling temperature (0.0 = deterministic).
        extra:       Provider-specific pass-through parameters.
    """

    model: str
    messages: list[dict[str, str]]
    max_tokens: int = 512
    temperature: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """Immutable response from a provider.

    Args:
        model:             Model that generated the response.
        content:           Generated text content.
        prompt_tokens:     Number of prompt tokens consumed.
        completion_tokens: Number of completion tokens generated.
        latency_s:         Wall-clock call duration in seconds.
        cost_usd:          Estimated cost in USD (0.0 if unknown).
        provider_name:     Name of the provider that served the request.
    """

    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    cost_usd: float = 0.0
    provider_name: str = ""


@dataclass
class Candidate:
    """A (provider, model) pair in a :class:`RoutingPolicy`.

    The ``model`` field overrides ``LLMRequest.model`` when this candidate is tried.
    """

    provider: Provider
    model: str


@dataclass
class RoutingPolicy:
    """Describes how to route an :class:`LLMRequest`.

    Args:
        candidates:    Ordered list of :class:`Candidate` entries to try.
        max_retries:   Number of *additional* attempts per candidate on failure
                       (total attempts per candidate = ``max_retries + 1``).
        backoff_base_s: Base delay in seconds for exponential backoff between
                        retries: ``backoff_base_s * 2 ** attempt``.
    """

    candidates: list[Candidate]
    max_retries: int = 2
    backoff_base_s: float = 0.1


class AllProvidersFailedError(Exception):
    """Raised when every candidate and its retries are exhausted.

    Args:
        errors: One :class:`BaseException` per failed attempt across all
                candidates and retries, in chronological order.
    """

    def __init__(self, errors: list[BaseException]) -> None:
        self.errors: list[BaseException] = errors
        super().__init__(
            f"{len(errors)} provider attempt(s) all failed; last error: {errors[-1]!r}"
            if errors
            else "No candidates tried."
        )
