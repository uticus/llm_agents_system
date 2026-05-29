"""Unit tests for the infra/inference_routing subsystem.

Covers T1–T10 as specified in task-003 §test-criteria.

All tests use an autouse fixture that resets the collector and registry.
No real network calls are made — all provider interaction goes through FakeProvider.
"""

from __future__ import annotations

import asyncio

import pytest

from llm_agents.infra.inference_routing import (
    AllProvidersFailedError,
    Candidate,
    FakeProvider,
    LLMRequest,
    LLMResponse,
    Router,
    RoutingPolicy,
)
from llm_agents.infra.observability import get_registry
from llm_agents.infra.tracing import get_collector
from llm_agents.infra.tracing._models import SpanKind, SpanStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    model: str = "fake-model",
    content: str = "Hello",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    latency_s: float = 0.01,
    cost_usd: float = 0.0,
    provider_name: str = "fake",
) -> LLMResponse:
    return LLMResponse(
        model=model,
        content=content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_s=latency_s,
        cost_usd=cost_usd,
        provider_name=provider_name,
    )


def _make_request(model: str = "gpt-4o") -> LLMRequest:
    return LLMRequest(model=model, messages=[{"role": "user", "content": "Hello"}])


def _make_router(*providers_and_models, export_hook=None, max_retries=0, backoff_base_s=0.0):
    """Build a Router from (FakeProvider, model_str) pairs."""
    candidates = [Candidate(provider=p, model=m) for p, m in providers_and_models]
    policy = RoutingPolicy(
        candidates=candidates,
        max_retries=max_retries,
        backoff_base_s=backoff_base_s,
    )
    return Router(policy=policy, export_hook=export_hook)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_infra():
    """Reset collector and registry state before and after each test."""
    get_collector().reset()
    get_registry().reset()
    yield
    get_collector().reset()
    get_registry().reset()


# ---------------------------------------------------------------------------
# T1 — Happy path
# ---------------------------------------------------------------------------


def test_happy_path_returns_response():
    """T1: Router routes to first candidate and returns its response."""
    resp = _make_response(model="gpt-4o", content="Hi there", provider_name="openai")
    provider = FakeProvider("openai", [resp])
    router = _make_router((provider, "gpt-4o"), export_hook=None)
    result = asyncio.run(router.complete(_make_request()))
    assert result.content == "Hi there"
    assert provider.call_count == 1


# ---------------------------------------------------------------------------
# T2 — Fallback
# ---------------------------------------------------------------------------


def test_fallback_to_second_candidate():
    """T2: First candidate always fails; router falls back to second; success."""
    err_provider = FakeProvider("bad", [RuntimeError("down")])
    good_resp = _make_response(model="claude-3", provider_name="anthropic")
    good_provider = FakeProvider("anthropic", [good_resp])
    router = _make_router(
        (err_provider, "bad-model"),
        (good_provider, "claude-3"),
        export_hook=None,
        max_retries=0,
    )
    result = asyncio.run(router.complete(_make_request()))
    assert result.model == "claude-3"
    assert good_provider.call_count == 1


# ---------------------------------------------------------------------------
# T3 — Retry on transient failure
# ---------------------------------------------------------------------------


def test_retry_on_transient_failure():
    """T3: Candidate fails twice then succeeds; router retries within max_retries."""
    good_resp = _make_response()
    provider = FakeProvider("p", [RuntimeError("transient"), RuntimeError("transient"), good_resp])
    router = _make_router((provider, "m"), export_hook=None, max_retries=2, backoff_base_s=0.0)
    result = asyncio.run(router.complete(_make_request()))
    assert result is good_resp
    assert provider.call_count == 3


# ---------------------------------------------------------------------------
# T4 — Max retries exceeded → AllProvidersFailedError
# ---------------------------------------------------------------------------


def test_all_providers_failed_error_raised():
    """T4: All candidates fail; AllProvidersFailedError raised with all errors."""
    e1 = RuntimeError("provider A down")
    e2 = ValueError("provider B invalid")
    p1 = FakeProvider("a", [e1])
    p2 = FakeProvider("b", [e2])
    router = _make_router((p1, "model-a"), (p2, "model-b"), export_hook=None, max_retries=0)
    with pytest.raises(AllProvidersFailedError) as exc_info:
        asyncio.run(router.complete(_make_request()))
    err = exc_info.value
    assert len(err.errors) == 2
    assert e1 in err.errors
    assert e2 in err.errors


def test_all_providers_failed_error_message():
    """T4b: AllProvidersFailedError has informative message."""
    p = FakeProvider("p", [RuntimeError("boom")])
    router = _make_router((p, "m"), export_hook=None, max_retries=0)
    with pytest.raises(AllProvidersFailedError) as exc_info:
        asyncio.run(router.complete(_make_request()))
    assert "1 provider attempt" in str(exc_info.value)


# ---------------------------------------------------------------------------
# T5 — Backoff: asyncio.sleep called with correct delay
# ---------------------------------------------------------------------------


def test_backoff_sleep_called_with_correct_delays(monkeypatch):
    """T5: asyncio.sleep is called with backoff_base * 2^attempt between retries."""
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    # Provider fails 2 times then succeeds (max_retries=2, backoff_base=0.1)
    provider = FakeProvider("p", [
        RuntimeError("fail"), RuntimeError("fail"), _make_response(),
    ])
    router = _make_router((provider, "m"), export_hook=None, max_retries=2, backoff_base_s=0.1)
    asyncio.run(router.complete(_make_request()))

    # Attempt 0 fails → sleep(0.1 * 2^0 = 0.1)
    # Attempt 1 fails → sleep(0.1 * 2^1 = 0.2)
    # Attempt 2 succeeds → no sleep
    assert sleep_calls == pytest.approx([0.1, 0.2])


# ---------------------------------------------------------------------------
# T6 — LLM span attributes
# ---------------------------------------------------------------------------


def test_llm_span_attributes_correct():
    """T6: After Router.complete(), a SpanKind.LLM span exists with correct attributes."""
    resp = _make_response(
        model="gpt-4o",
        prompt_tokens=20,
        completion_tokens=10,
        cost_usd=0.001,
        provider_name="openai",
    )
    provider = FakeProvider("openai", [resp])
    router = _make_router((provider, "gpt-4o"), export_hook=None)
    asyncio.run(router.complete(_make_request()))

    collector = get_collector()
    all_spans = [s for t in collector.all_traces() for s in t.spans]
    llm_spans = [s for s in all_spans if s.kind == SpanKind.LLM]
    assert len(llm_spans) == 1
    span = llm_spans[0]
    assert span.attributes["model"] == "gpt-4o"
    assert span.attributes["provider"] == "openai"
    assert span.attributes["prompt_tokens"] == 20
    assert span.attributes["completion_tokens"] == 10
    assert span.attributes["cost_usd"] == pytest.approx(0.001)
    assert "latency_s" in span.attributes
    assert span.status == SpanStatus.OK


def test_llm_span_attributes_on_error():
    """T6b: Failed LLM span has ERROR status and 'error' attribute."""
    exc = RuntimeError("timeout")
    provider = FakeProvider("p", [exc])
    router = _make_router((provider, "m"), export_hook=None, max_retries=0)

    with pytest.raises(AllProvidersFailedError):
        asyncio.run(router.complete(_make_request()))

    collector = get_collector()
    all_spans = [s for t in collector.all_traces() for s in t.spans]
    llm_spans = [s for s in all_spans if s.kind == SpanKind.LLM]
    assert len(llm_spans) == 1
    assert llm_spans[0].status == SpanStatus.ERROR
    assert "timeout" in llm_spans[0].attributes["error"]


# ---------------------------------------------------------------------------
# T7 — Outer routing span
# ---------------------------------------------------------------------------


def test_outer_routing_span_exists():
    """T7: Outer routing span of kind AGENT is emitted for each Router.complete() call."""
    provider = FakeProvider("p", [_make_response()])
    router = _make_router((provider, "m"), export_hook=None)
    asyncio.run(router.complete(_make_request()))

    collector = get_collector()
    all_spans = [s for t in collector.all_traces() for s in t.spans]
    agent_spans = [s for s in all_spans if s.kind == SpanKind.AGENT]
    assert len(agent_spans) == 1
    assert agent_spans[0].name == "routing"
    assert agent_spans[0].attributes["policy_candidates"] == 1
    assert agent_spans[0].status == SpanStatus.OK


def test_outer_span_error_on_all_failed():
    """T7b: Outer routing span has ERROR status when all candidates fail."""
    provider = FakeProvider("p", [RuntimeError("down")])
    router = _make_router((provider, "m"), export_hook=None, max_retries=0)

    with pytest.raises(AllProvidersFailedError):
        asyncio.run(router.complete(_make_request()))

    collector = get_collector()
    all_spans = [s for t in collector.all_traces() for s in t.spans]
    agent_spans = [s for s in all_spans if s.kind == SpanKind.AGENT]
    assert agent_spans[0].status == SpanStatus.ERROR


# ---------------------------------------------------------------------------
# T8 — FakeProvider sequential playback
# ---------------------------------------------------------------------------


def test_fake_provider_sequential_responses():
    """T8: FakeProvider returns responses in sequence then repeats last when exhausted."""
    r1 = _make_response(content="first")
    r2 = _make_response(content="second")
    provider = FakeProvider("p", [r1, r2])

    results = [asyncio.run(provider.complete(_make_request())) for _ in range(4)]
    assert results[0].content == "first"
    assert results[1].content == "second"
    assert results[2].content == "second"  # last repeated
    assert results[3].content == "second"


# ---------------------------------------------------------------------------
# T9 — FakeProvider raises
# ---------------------------------------------------------------------------


def test_fake_provider_raises_exception():
    """T9: FakeProvider raises the exception configured at the given index."""
    exc = ValueError("bad request")
    provider = FakeProvider("p", [exc])
    with pytest.raises(ValueError, match="bad request"):
        asyncio.run(provider.complete(_make_request()))


def test_fake_provider_raises_then_returns():
    """T9b: FakeProvider can raise on first call then succeed on second."""
    exc = RuntimeError("transient")
    good = _make_response()
    provider = FakeProvider("p", [exc, good])
    with pytest.raises(RuntimeError):
        asyncio.run(provider.complete(_make_request()))
    result = asyncio.run(provider.complete(_make_request()))
    assert result is good


# ---------------------------------------------------------------------------
# T10 — bridge_span wiring: observability registry updated
# ---------------------------------------------------------------------------


def test_bridge_span_wiring_updates_registry():
    """T10: With default export_hook, spans_total counter is incremented after complete()."""
    from llm_agents.infra.observability import bridge_span

    provider = FakeProvider("p", [_make_response()])
    router = _make_router((provider, "m"), export_hook=bridge_span)
    asyncio.run(router.complete(_make_request()))

    reg = get_registry()
    output = reg.export()
    # At minimum, spans_total should be present (both LLM and AGENT spans were bridged)
    assert "llm_agents_spans_total" in output
