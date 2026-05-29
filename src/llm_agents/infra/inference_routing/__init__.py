"""Inference routing subsystem: uniform LLM dispatch with retry and failover.

Public surface
--------------
Data model::

    from llm_agents.infra.inference_routing import (
        LLMRequest, LLMResponse, Candidate, RoutingPolicy, AllProvidersFailedError,
    )

Provider protocol and fake::

    from llm_agents.infra.inference_routing import Provider, FakeProvider

Router::

    from llm_agents.infra.inference_routing import Router

    policy = RoutingPolicy(candidates=[Candidate(provider=my_provider, model="gpt-4o")])
    router = Router(policy)
    response = await router.complete(request)

See :mod:`llm_agents.infra.inference_routing._models`,
:mod:`llm_agents.infra.inference_routing._provider`, and
:mod:`llm_agents.infra.inference_routing._router` for implementation details.
"""

from llm_agents.infra.inference_routing._models import (
    AllProvidersFailedError,
    Candidate,
    LLMRequest,
    LLMResponse,
    RoutingPolicy,
)
from llm_agents.infra.inference_routing._provider import FakeProvider, Provider
from llm_agents.infra.inference_routing._router import Router

__all__ = [
    "AllProvidersFailedError",
    "Candidate",
    "FakeProvider",
    "LLMRequest",
    "LLMResponse",
    "Provider",
    "Router",
    "RoutingPolicy",
]
