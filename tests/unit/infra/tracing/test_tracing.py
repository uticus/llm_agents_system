"""Unit tests for llm_agents.infra.tracing.

All tests are self-contained (no network, no I/O beyond in-process memory).
Each test resets the collector to guarantee isolation.
"""

from __future__ import annotations

import asyncio
import warnings

import pytest

from llm_agents.infra.tracing import (
    SCHEMA_VERSION,
    FinishedSpan,
    SpanKind,
    SpanStatus,
    Trace,
    current_span,
    deserialize_trace,
    get_collector,
    serialize_trace,
    traced,
    tracer,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_collector():
    """Reset the global collector before every test."""
    get_collector().reset()
    yield
    get_collector().reset()


# ---------------------------------------------------------------------------
# T1 — Single span: basic fields
# ---------------------------------------------------------------------------


def test_single_span_basic_fields():
    with tracer.span("op", SpanKind.INTERNAL, key="val") as span:
        assert current_span() is span

    traces = get_collector().all_traces()
    assert len(traces) == 1
    finished: FinishedSpan = traces[0].spans[0]

    assert finished.name == "op"
    assert finished.kind == SpanKind.INTERNAL
    assert finished.status == SpanStatus.OK
    assert finished.attributes["key"] == "val"
    assert finished.parent_id is None
    assert len(finished.trace_id) == 32 and finished.trace_id.isalnum()
    assert len(finished.span_id) == 32 and finished.span_id.isalnum()
    assert finished.duration_s >= 0.0
    assert finished.start_wall  # non-empty ISO-8601 string


# ---------------------------------------------------------------------------
# T2 — Nested sync spans: parent-child chain
# ---------------------------------------------------------------------------


def test_nested_sync_spans_parent_child():
    with tracer.span("outer") as outer_span:
        outer_id = outer_span.span_id
        outer_trace = outer_span.trace_id
        with tracer.span("inner") as inner_span:
            assert inner_span.parent_id == outer_id
            assert inner_span.trace_id == outer_trace

    spans = get_collector().all_traces()[0].spans
    assert len(spans) == 2

    inner_f = next(s for s in spans if s.name == "inner")
    outer_f = next(s for s in spans if s.name == "outer")

    assert inner_f.parent_id == outer_f.span_id
    assert outer_f.parent_id is None
    assert inner_f.trace_id == outer_f.trace_id
    assert inner_f.span_id != outer_f.span_id


# ---------------------------------------------------------------------------
# T3 — Nested async spans: async context manager
# ---------------------------------------------------------------------------


def test_nested_async_spans():
    async def run():
        async with tracer.span("outer") as outer_span:
            outer_id = outer_span.span_id
            outer_trace = outer_span.trace_id
            async with tracer.span("inner") as inner_span:
                assert inner_span.parent_id == outer_id
                assert inner_span.trace_id == outer_trace

    asyncio.run(run())

    spans = get_collector().all_traces()[0].spans
    assert len(spans) == 2

    inner_f = next(s for s in spans if s.name == "inner")
    outer_f = next(s for s in spans if s.name == "outer")

    assert inner_f.parent_id == outer_f.span_id
    assert outer_f.parent_id is None
    assert inner_f.trace_id == outer_f.trace_id


# ---------------------------------------------------------------------------
# T4 — Error span: exception sets status and attribute
# ---------------------------------------------------------------------------


def test_error_span_sets_status_and_attribute():
    with pytest.raises(ValueError, match="boom"):
        with tracer.span("fail"):
            raise ValueError("boom")

    finished = get_collector().all_traces()[0].spans[0]
    assert finished.status == SpanStatus.ERROR
    assert finished.attributes["error"] == "boom"


# ---------------------------------------------------------------------------
# T5 — @traced decorator on sync function
# ---------------------------------------------------------------------------


def test_traced_decorator_sync():
    @tracer.traced("my_op", SpanKind.TOOL)
    def work(x: int) -> int:
        return x * 2

    result = work(21)

    assert result == 42
    finished = get_collector().all_traces()[0].spans[0]
    assert finished.name == "my_op"
    assert finished.kind == SpanKind.TOOL
    assert finished.status == SpanStatus.OK


# ---------------------------------------------------------------------------
# T6 — @traced decorator on async function
# ---------------------------------------------------------------------------


def test_traced_decorator_async():
    @tracer.traced(kind=SpanKind.LLM)
    async def async_work(x: int) -> int:
        return x + 1

    result = asyncio.run(async_work(41))

    assert result == 42
    finished = get_collector().all_traces()[0].spans[0]
    # name defaults to __qualname__
    assert "async_work" in finished.name
    assert finished.kind == SpanKind.LLM
    assert finished.status == SpanStatus.OK


# ---------------------------------------------------------------------------
# T7 — LLM-call attributes: all standard fields captured
# ---------------------------------------------------------------------------


def test_llm_call_attributes():
    with tracer.span(
        "llm_call",
        SpanKind.LLM,
        model="gpt-4o",
        prompt_tokens=100,
        completion_tokens=50,
        latency_s=0.42,
        cost_usd=0.001,
    ):
        pass

    attrs = get_collector().all_traces()[0].spans[0].attributes
    assert attrs["model"] == "gpt-4o"
    assert attrs["prompt_tokens"] == 100
    assert attrs["completion_tokens"] == 50
    assert attrs["latency_s"] == pytest.approx(0.42)
    assert attrs["cost_usd"] == pytest.approx(0.001)


# ---------------------------------------------------------------------------
# T8 — Serialization round-trip
# ---------------------------------------------------------------------------


def test_serialization_round_trip():
    with tracer.span("outer", SpanKind.AGENT, tag="root"):
        with tracer.span("inner", SpanKind.TOOL, items=3):
            pass

    original_trace = get_collector().all_traces()[0]
    serialized = serialize_trace(original_trace)

    assert serialized["schema_version"] == SCHEMA_VERSION
    assert serialized["trace_id"] == original_trace.trace_id

    restored = deserialize_trace(serialized)
    assert restored == original_trace


# ---------------------------------------------------------------------------
# T9a — Schema version warning
# ---------------------------------------------------------------------------


def test_deserialize_unknown_schema_version_warns():
    with tracer.span("op"):
        pass

    data = serialize_trace(get_collector().all_traces()[0])
    data["schema_version"] = 99

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = deserialize_trace(data)

    assert any("schema_version" in str(w.message) for w in caught)
    assert isinstance(result, Trace)


# ---------------------------------------------------------------------------
# T9b — Missing required field raises ValueError
# ---------------------------------------------------------------------------


def test_deserialize_missing_field_raises_value_error():
    with tracer.span("op"):
        pass

    data = serialize_trace(get_collector().all_traces()[0])
    del data["trace_id"]

    with pytest.raises(ValueError, match="trace_id"):
        deserialize_trace(data)


# ---------------------------------------------------------------------------
# T10a — Export hook called for each span
# ---------------------------------------------------------------------------


def test_export_hook_called_per_span():
    received: list[FinishedSpan] = []
    get_collector().set_export_hook(received.append)

    with tracer.span("span1"):
        pass
    with tracer.span("span2"):
        pass

    assert len(received) == 2
    assert all(isinstance(s, FinishedSpan) for s in received)
    assert {s.name for s in received} == {"span1", "span2"}


# ---------------------------------------------------------------------------
# T10b — Hook exception is isolated
# ---------------------------------------------------------------------------


def test_export_hook_exception_does_not_propagate():
    def bad_hook(span: FinishedSpan) -> None:
        raise RuntimeError("hook fail")

    get_collector().set_export_hook(bad_hook)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with tracer.span("op"):
            pass  # should not raise despite bad hook

    # span is still recorded
    assert len(get_collector().all_traces()) == 1
    # warning was emitted
    assert any("hook fail" in str(w.message) for w in caught)


# ---------------------------------------------------------------------------
# Module-level traced convenience export
# ---------------------------------------------------------------------------


def test_module_level_traced_is_usable():
    """The module-level ``traced`` alias works identically to tracer.traced."""

    @traced("mod_level_op", SpanKind.INTERNAL)
    def fn() -> int:
        return 42

    result = fn()
    assert result == 42
    finished = get_collector().all_traces()[0].spans[0]
    assert finished.name == "mod_level_op"
    assert finished.status == SpanStatus.OK


# ---------------------------------------------------------------------------
# T11 — Concurrent async tasks: context isolation
# ---------------------------------------------------------------------------


def test_concurrent_async_context_isolation():
    results: dict[str, str | None] = {}

    async def task_a():
        async with tracer.span("A-span"):
            await asyncio.sleep(0)  # yield to event loop
            results["a"] = current_span().name if current_span() else None

    async def task_b():
        async with tracer.span("B-span"):
            await asyncio.sleep(0)
            results["b"] = current_span().name if current_span() else None

    async def run():
        await asyncio.gather(task_a(), task_b())

    asyncio.run(run())

    assert results["a"] == "A-span", f"task A saw: {results['a']}"
    assert results["b"] == "B-span", f"task B saw: {results['b']}"

    # both spans recorded; each is a root span
    all_spans = [s for t in get_collector().all_traces() for s in t.spans]
    assert len(all_spans) == 2
    assert all(s.parent_id is None for s in all_spans)
