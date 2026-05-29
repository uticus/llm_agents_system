"""In-memory completion cache with TTL expiry and optional LRU eviction.

:class:`CompletionCache` stores :class:`~llm_agents.infra.inference_routing.LLMResponse`
objects keyed on an exact-match hash of the request parameters.  Stale entries
expire after ``ttl_s`` seconds.  When ``max_size`` is set, the least-recently-used
entry is evicted when the limit is exceeded.

Cache hits skip the provider call entirely; use ``force_refresh=True`` on
:meth:`CompletionCache.cached_complete` to bypass the cache for one call.

Cache key covers: ``model``, ``messages``, ``max_tokens``, ``temperature``.
The ``extra`` field is intentionally excluded — callers that pass provider-specific
extra params are expected to manage bypass themselves via ``force_refresh``.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict

from llm_agents.infra.inference_routing._models import LLMRequest, LLMResponse
from llm_agents.infra.inference_routing._router import Router


def _cache_key(request: LLMRequest) -> str:
    """Return a hex-digest cache key for *request*.

    Uses MD5 (non-security context — fast collision-resistant key generation).
    """
    payload = json.dumps(
        {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        },
        sort_keys=True,
    ).encode()
    return hashlib.md5(payload).hexdigest()  # noqa: S324


class CompletionCache:
    """In-memory LRU cache for LLM completions with TTL-based expiry.

    Args:
        ttl_s:    Time-to-live in seconds for each cached entry.  Default 300 s.
        max_size: Maximum number of entries.  When exceeded, the oldest entry
                  (least recently used) is evicted.  ``None`` means unbounded.
    """

    def __init__(self, ttl_s: float = 300.0, max_size: int | None = None) -> None:
        self._ttl_s = ttl_s
        self._max_size = max_size
        # (response, expire_at_monotonic)
        self._store: OrderedDict[str, tuple[LLMResponse, float]] = OrderedDict()

    def get(self, request: LLMRequest) -> LLMResponse | None:
        """Return the cached :class:`LLMResponse` for *request*, or ``None`` on miss/expiry."""
        key = _cache_key(request)
        entry = self._store.get(key)
        if entry is None:
            return None
        response, expire_at = entry
        if time.monotonic() > expire_at:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return response

    def set(self, request: LLMRequest, response: LLMResponse) -> None:
        """Store *response* in the cache for *request*.

        If ``max_size`` is set, the least-recently-used entry is evicted when
        the store exceeds the limit.
        """
        key = _cache_key(request)
        expire_at = time.monotonic() + self._ttl_s
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (response, expire_at)
        if self._max_size is not None:
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def clear(self) -> None:
        """Remove all cached entries."""
        self._store.clear()

    async def cached_complete(
        self,
        request: LLMRequest,
        router: Router,
        *,
        force_refresh: bool = False,
    ) -> LLMResponse:
        """Return a cached response or route the *request* and cache the result.

        Args:
            request:       The LLM request.
            router:        Routing layer used on cache miss.
            force_refresh: When ``True``, bypass the cache for this call and
                           update the cache with the fresh response.

        Returns:
            An :class:`LLMResponse`, either from cache or from the router.
        """
        if not force_refresh:
            cached = self.get(request)
            if cached is not None:
                return cached
        response = await router.complete(request)
        self.set(request, response)
        return response
