"""Request batcher: dispatch a list of LLM requests concurrently.

:class:`Batcher` wraps a :class:`~llm_agents.infra.inference_routing.Router` and
dispatches multiple :class:`~llm_agents.infra.inference_routing.LLMRequest` objects
concurrently via :func:`asyncio.gather`.  Each slot in the returned list holds
either an :class:`~llm_agents.infra.inference_routing.LLMResponse` or the
:class:`BaseException` raised for that request — exceptions are not re-raised.

Usage::

    batcher = Batcher(router)
    results = await batcher.batch_complete([req1, req2, req3])
    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            print(f"Request {i} failed: {result}")
        else:
            print(f"Request {i}: {result.content[:80]}")
"""

from __future__ import annotations

import asyncio

from llm_agents.infra.inference_routing._models import LLMRequest, LLMResponse
from llm_agents.infra.inference_routing._router import Router


class Batcher:
    """Concurrent LLM request dispatcher.

    Args:
        router: The :class:`Router` to use for each individual request.
    """

    def __init__(self, router: Router) -> None:
        self._router = router

    async def batch_complete(
        self,
        requests: list[LLMRequest],
    ) -> list[LLMResponse | BaseException]:
        """Dispatch all *requests* concurrently and return results in input order.

        Uses :func:`asyncio.gather` with ``return_exceptions=True`` so that a
        failure in one slot does not cancel the others.  The returned list has
        the same length and order as *requests*.

        Args:
            requests: List of :class:`LLMRequest` objects to dispatch.

        Returns:
            A list where each element is either an :class:`LLMResponse` or the
            :class:`BaseException` raised for that request.
        """
        if not requests:
            return []
        coroutines = [self._router.complete(r) for r in requests]
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        return list(results)
