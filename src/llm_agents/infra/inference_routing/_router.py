"""Router: async LLM routing with retry, backoff, and ordered failover.

Each :class:`Router` instance holds a :class:`RoutingPolicy` and dispatches
:class:`LLMRequest` objects through the policy's ordered candidate list.  On
transient failure it retries with exponential backoff; on persistent failure it
moves to the next candidate; when all candidates are exhausted it raises
:class:`AllProvidersFailedError`.

Every individual provider attempt is traced as a ``SpanKind.LLM`` span.  The
outer routing call is traced as a ``SpanKind.AGENT`` span.  Observability metrics
are updated automatically via the ``bridge_span`` export hook registered on the
:class:`InMemoryCollector` singleton.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import replace

from llm_agents.infra.inference_routing._models import (
    AllProvidersFailedError,
    LLMRequest,
    LLMResponse,
    RoutingPolicy,
)
from llm_agents.infra.observability import bridge_span as _default_bridge
from llm_agents.infra.tracing import get_collector, tracer
from llm_agents.infra.tracing._models import FinishedSpan, SpanKind, SpanStatus


class Router:
    """Async LLM router.

    Args:
        policy:      Describes candidates, retry count, and backoff parameters.
        export_hook: Called with each finished :class:`FinishedSpan`.  Defaults
                     to :func:`bridge_span` which updates the observability
                     registry.  Pass ``None`` to disable hook registration (useful
                     in tests that manage the collector hook themselves).
    """

    def __init__(
        self,
        policy: RoutingPolicy,
        export_hook: Callable[[FinishedSpan], None] | None = _default_bridge,
    ) -> None:
        self._policy = policy
        if export_hook is not None:
            get_collector().set_export_hook(export_hook)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Route *request* through the policy and return the first successful response.

        Tries each :class:`Candidate` in order.  For each candidate it makes up
        to ``policy.max_retries + 1`` attempts, sleeping ``policy.backoff_base_s
        * 2 ** attempt`` seconds between retries.

        Returns:
            The :class:`LLMResponse` from the first successful provider call.

        Raises:
            AllProvidersFailedError: When every candidate and all retries are
                exhausted.
        """
        policy = self._policy
        all_errors: list[BaseException] = []

        async with tracer.span(
            "routing",
            kind=SpanKind.AGENT,
            policy_candidates=len(policy.candidates),
        ) as outer_span:
            for candidate in policy.candidates:
                for attempt in range(policy.max_retries + 1):
                    async with tracer.span(
                        "llm_call",
                        kind=SpanKind.LLM,
                        model=candidate.model,
                        provider=candidate.provider.name,
                    ) as span:
                        try:
                            req = replace(request, model=candidate.model)
                            t0 = time.perf_counter()
                            response = await candidate.provider.complete(req)
                            latency = time.perf_counter() - t0
                            span.attributes.update(
                                model=candidate.model,
                                provider=candidate.provider.name,
                                prompt_tokens=response.prompt_tokens,
                                completion_tokens=response.completion_tokens,
                                latency_s=latency,
                                cost_usd=response.cost_usd,
                            )
                            span.status = SpanStatus.OK
                            outer_span.status = SpanStatus.OK
                            return response

                        except Exception as exc:  # noqa: BLE001
                            span.status = SpanStatus.ERROR
                            span.attributes["error"] = str(exc)
                            all_errors.append(exc)
                            if attempt < policy.max_retries:
                                await asyncio.sleep(
                                    policy.backoff_base_s * (2**attempt)
                                )

            outer_span.status = SpanStatus.ERROR
            outer_span.attributes["error"] = f"{len(all_errors)} attempts failed"

        raise AllProvidersFailedError(all_errors)
