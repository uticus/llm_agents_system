"""Unit tests for infra/cost_latency_optimization.

Covers T1–T9 as specified in task-004 §test-criteria.
No real network calls are made.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from llm_agents.infra.cost_latency_optimization import (
    Batcher,
    BudgetTracker,
    CompletionCache,
)
from llm_agents.infra.inference_routing import (
    AllProvidersFailedError,
    Candidate,
    FakeProvider,
    LLMRequest,
    LLMResponse,
    Router,
    RoutingPolicy,
)
from llm_agents.infra.tracing import get_collector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resp(
    *,
    model: str = "m",
    content: str = "ok",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    cost_usd: float = 0.001,
) -> LLMResponse:
    return LLMResponse(
        model=model,
        content=content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_s=0.01,
        cost_usd=cost_usd,
    )


def _req(model: str = "gpt-4o", content: str = "Hello") -> LLMRequest:
    return LLMRequest(model=model, messages=[{"role": "user", "content": content}])


def _router(provider: FakeProvider, model: str = "m") -> Router:
    policy = RoutingPolicy(
        candidates=[Candidate(provider=provider, model=model)],
        max_retries=0,
    )
    return Router(policy=policy, export_hook=None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_collector():
    get_collector().reset()
    yield
    get_collector().reset()


# ---------------------------------------------------------------------------
# T1 — Cache hit avoids provider call
# ---------------------------------------------------------------------------


def test_cache_hit_avoids_provider_call():
    """T1: After first call, cache hit returns cached response; provider called once."""
    provider = FakeProvider("p", [_resp(content="cached")])
    router = _router(provider)
    cache = CompletionCache(ttl_s=60.0)
    req = _req()

    r1 = asyncio.run(cache.cached_complete(req, router))
    r2 = asyncio.run(cache.cached_complete(req, router))

    assert r1.content == "cached"
    assert r2.content == "cached"
    assert provider.call_count == 1  # provider called only once


# ---------------------------------------------------------------------------
# T2 — Cache miss falls through to routing
# ---------------------------------------------------------------------------


def test_cache_miss_calls_provider():
    """T2: First call is a cache miss; provider is called and result is cached."""
    provider = FakeProvider("p", [_resp(content="fresh")])
    router = _router(provider)
    cache = CompletionCache(ttl_s=60.0)
    req = _req()

    result = asyncio.run(cache.cached_complete(req, router))
    assert result.content == "fresh"
    assert provider.call_count == 1


# ---------------------------------------------------------------------------
# T3 — Force refresh bypass
# ---------------------------------------------------------------------------


def test_force_refresh_bypasses_cache():
    """T3: force_refresh=True calls provider again even when cache has an entry."""
    r1 = _resp(content="first")
    r2 = _resp(content="second")
    provider = FakeProvider("p", [r1, r2])
    router = _router(provider)
    cache = CompletionCache(ttl_s=60.0)
    req = _req()

    asyncio.run(cache.cached_complete(req, router))  # populates cache
    result = asyncio.run(cache.cached_complete(req, router, force_refresh=True))  # bypass
    assert result.content == "second"
    assert provider.call_count == 2


# ---------------------------------------------------------------------------
# T4 — TTL expiry causes cache miss
# ---------------------------------------------------------------------------


def test_ttl_expiry_causes_miss():
    """T4: After TTL expires, get() returns None."""
    cache = CompletionCache(ttl_s=0.001)  # 1 ms TTL
    req = _req()
    cache.set(req, _resp())
    time.sleep(0.05)  # wait for expiry
    assert cache.get(req) is None


def test_ttl_not_yet_expired_returns_response():
    """T4b: Entry within TTL is returned."""
    cache = CompletionCache(ttl_s=60.0)
    req = _req()
    resp = _resp()
    cache.set(req, resp)
    assert cache.get(req) is resp


# ---------------------------------------------------------------------------
# T5 — LRU eviction
# ---------------------------------------------------------------------------


def test_lru_eviction_on_max_size():
    """T5: max_size=2; third entry evicts the oldest; evicted entry returns None on get."""
    cache = CompletionCache(ttl_s=60.0, max_size=2)
    req_a = _req(content="A")
    req_b = _req(content="B")
    req_c = _req(content="C")

    cache.set(req_a, _resp(content="A"))
    cache.set(req_b, _resp(content="B"))
    cache.set(req_c, _resp(content="C"))  # should evict req_a

    assert cache.get(req_a) is None  # evicted
    assert cache.get(req_b) is not None
    assert cache.get(req_c) is not None


def test_lru_access_prevents_eviction():
    """T5b: Accessing req_a after req_b prevents req_a from being evicted when req_c added."""
    cache = CompletionCache(ttl_s=60.0, max_size=2)
    req_a = _req(content="A")
    req_b = _req(content="B")
    req_c = _req(content="C")

    cache.set(req_a, _resp(content="A"))
    cache.set(req_b, _resp(content="B"))
    cache.get(req_a)  # access A → moves it to "most recent"
    cache.set(req_c, _resp(content="C"))  # should evict req_b (least recently used)

    assert cache.get(req_b) is None  # req_b evicted
    assert cache.get(req_a) is not None  # req_a still present
    assert cache.get(req_c) is not None  # req_c present


# ---------------------------------------------------------------------------
# T6 — Batcher happy path
# ---------------------------------------------------------------------------


def test_batcher_happy_path():
    """T6: batch_complete returns list of length == len(requests); all succeed."""
    r1 = _resp(content="one")
    r2 = _resp(content="two")
    provider = FakeProvider("p", [r1, r2])
    router = _router(provider)
    batcher = Batcher(router)

    req1 = _req(content="first")
    req2 = _req(content="second")
    results = asyncio.run(batcher.batch_complete([req1, req2]))

    assert len(results) == 2
    assert all(isinstance(r, LLMResponse) for r in results)
    assert provider.call_count == 2


def test_batcher_empty_input():
    """T6b: batch_complete([]) returns []."""
    provider = FakeProvider("p", [_resp()])
    router = _router(provider)
    batcher = Batcher(router)
    results = asyncio.run(batcher.batch_complete([]))
    assert results == []


# ---------------------------------------------------------------------------
# T7 — Batcher per-slot exception
# ---------------------------------------------------------------------------


def test_batcher_per_slot_exception():
    """T7: One slot fails; exception returned in that slot; other slot succeeds; no raise."""
    good = _resp(content="good")
    # Use a single FakeProvider that returns a good response then raises on second call.
    provider_mixed = FakeProvider("mixed", [good, RuntimeError("fail")])
    policy_mixed = RoutingPolicy(
        candidates=[Candidate(provider=provider_mixed, model="m")],
        max_retries=0,
    )
    router_mixed = Router(policy=policy_mixed, export_hook=None)
    batcher = Batcher(router_mixed)

    results = asyncio.run(batcher.batch_complete([_req(content="ok"), _req(content="bad")]))
    assert len(results) == 2
    assert isinstance(results[0], LLMResponse)
    assert isinstance(results[1], (AllProvidersFailedError, Exception))


# ---------------------------------------------------------------------------
# T8 — BudgetTracker track + report
# ---------------------------------------------------------------------------


def test_budget_tracker_report_totals():
    """T8: track two responses; report totals are correct."""
    tracker = BudgetTracker()
    tracker.track(_resp(prompt_tokens=100, completion_tokens=50, cost_usd=0.002))
    tracker.track(_resp(prompt_tokens=200, completion_tokens=100, cost_usd=0.004))

    report = tracker.report()
    assert report.prompt_tokens == 300
    assert report.completion_tokens == 150
    assert report.total_tokens == 450
    assert report.cost_usd == pytest.approx(0.006)
    assert report.call_count == 2


def test_budget_tracker_total_tokens_invariant():
    """T8b: total_tokens == prompt_tokens + completion_tokens."""
    tracker = BudgetTracker()
    tracker.track(_resp(prompt_tokens=7, completion_tokens=3, cost_usd=0.0))
    report = tracker.report()
    assert report.total_tokens == report.prompt_tokens + report.completion_tokens


# ---------------------------------------------------------------------------
# T9 — BudgetTracker reset
# ---------------------------------------------------------------------------


def test_budget_tracker_reset():
    """T9: After reset(), report() returns all zeros."""
    tracker = BudgetTracker()
    tracker.track(_resp(prompt_tokens=50, completion_tokens=25, cost_usd=0.001))
    tracker.reset()
    report = tracker.report()
    assert report.prompt_tokens == 0
    assert report.completion_tokens == 0
    assert report.total_tokens == 0
    assert report.cost_usd == 0.0
    assert report.call_count == 0
