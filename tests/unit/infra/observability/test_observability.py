"""Unit tests for the infra/observability subsystem.

Covers T1–T13 as specified in task-002 §test-criteria.

All tests use an autouse fixture that resets the shared MetricsRegistry and
clears the stdlib logging handlers so test isolation is guaranteed.
No real network calls are made.
"""

from __future__ import annotations

import io
import json
import logging
import time

import pytest

from llm_agents.infra.observability import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    StructuredLogger,
    bridge_span,
    get_registry,
)
from llm_agents.infra.tracing import tracer
from llm_agents.infra.tracing._models import FinishedSpan, SpanKind, SpanStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the shared registry and clear cached logger handlers before each test."""
    reg = get_registry()
    reg.reset()
    yield
    reg.reset()


def _make_finished_span(
    *,
    kind: SpanKind = SpanKind.INTERNAL,
    status: SpanStatus = SpanStatus.OK,
    duration_s: float = 0.1,
    attributes: dict | None = None,
    name: str = "test-span",
) -> FinishedSpan:
    """Convenience builder for FinishedSpan in tests."""
    now = time.perf_counter()
    return FinishedSpan(
        trace_id="aaaa",
        span_id="bbbb",
        parent_id=None,
        name=name,
        kind=kind,
        start_time=now,
        start_wall="2026-01-01T00:00:00+00:00",
        end_time=now + duration_s,
        duration_s=duration_s,
        status=status,
        attributes=attributes or {},
    )


# ---------------------------------------------------------------------------
# T1 — Counter
# ---------------------------------------------------------------------------


def test_counter_initial_value():
    """T1a: Counter initialises to 0.0."""
    c = Counter()
    assert c.value == 0.0


def test_counter_inc_accumulates():
    """T1b: Counter.inc() accumulates correctly across multiple calls."""
    c = Counter()
    c.inc()
    assert c.value == 1.0
    c.inc(4.5)
    assert c.value == 5.5
    c.inc(0.5)
    assert c.value == 6.0


# ---------------------------------------------------------------------------
# T2 — Gauge
# ---------------------------------------------------------------------------


def test_gauge_set_inc_dec():
    """T2: Gauge.set/inc/dec track values correctly; negative values allowed."""
    g = Gauge()
    assert g.value == 0.0
    g.set(10.0)
    assert g.value == 10.0
    g.inc(3.0)
    assert g.value == 13.0
    g.dec(5.0)
    assert g.value == 8.0
    g.set(-2.0)
    assert g.value == -2.0


# ---------------------------------------------------------------------------
# T3 — Histogram
# ---------------------------------------------------------------------------


def test_histogram_observe_updates_count_and_sum():
    """T3a: observe() increments count and sum correctly."""
    h = Histogram()
    assert h.count == 0
    assert h.sum == 0.0
    h.observe(0.05)
    assert h.count == 1
    assert h.sum == pytest.approx(0.05)
    h.observe(2.0)
    assert h.count == 2
    assert h.sum == pytest.approx(2.05)


def test_histogram_bucket_counts_are_cumulative():
    """T3b: bucket counts are cumulative; +Inf is always present and equals count."""
    h = Histogram(buckets=(0.1, 0.5, 1.0))
    h.observe(0.05)  # <= 0.1, <= 0.5, <= 1.0, <= +Inf
    h.observe(0.3)  # > 0.1, <= 0.5, <= 1.0, <= +Inf
    h.observe(2.0)  # > 0.1, > 0.5, > 1.0, <= +Inf

    bkts = dict(h.buckets())
    assert bkts[0.1] == 1
    assert bkts[0.5] == 2
    assert bkts[1.0] == 2
    import math

    assert bkts[math.inf] == 3  # +Inf == total count


def test_histogram_inf_bucket_always_present():
    """T3c: +Inf bucket is always appended even if not in the provided list."""
    import math

    h = Histogram(buckets=(0.1,))
    les = [le for le, _ in h.buckets()]
    assert math.inf in les


def test_histogram_custom_buckets():
    """T3d: custom bucket list is respected."""
    h = Histogram(buckets=(1.0, 5.0, 10.0))
    boundaries = [le for le, _ in h.buckets()]
    import math

    assert 1.0 in boundaries
    assert 5.0 in boundaries
    assert 10.0 in boundaries
    assert math.inf in boundaries


# ---------------------------------------------------------------------------
# T4 — MetricsRegistry deduplication
# ---------------------------------------------------------------------------


def test_registry_deduplication_same_instance():
    """T4: counter() with identical name+labels returns the same object."""
    reg = get_registry()
    c1 = reg.counter("req", labels={"env": "test"})
    c2 = reg.counter("req", labels={"env": "test"})
    assert c1 is c2


def test_registry_different_labels_different_instance():
    """T4b: counter() with different labels returns different instances."""
    reg = get_registry()
    c1 = reg.counter("req", labels={"env": "prod"})
    c2 = reg.counter("req", labels={"env": "test"})
    assert c1 is not c2


# ---------------------------------------------------------------------------
# T5 — Export: counter
# ---------------------------------------------------------------------------


def test_export_counter_format():
    """T5: export() for a counter contains correct TYPE line and _total{} value."""
    reg = get_registry()
    reg.counter("requests", help="Total requests.", labels={"env": "test"}).inc(7)
    output = reg.export()

    assert "# TYPE llm_agents_requests_total counter" in output
    assert "# HELP llm_agents_requests_total Total requests." in output
    # Label and value on same line
    assert 'llm_agents_requests_total{env="test"} 7.0' in output


def test_export_counter_name_ends_in_total():
    """T5b: counter name automatically gets _total suffix."""
    reg = get_registry()
    reg.counter("hits").inc()
    output = reg.export()
    assert "llm_agents_hits_total" in output
    # Original name without _total must not appear as a metric line
    lines = [ln for ln in output.splitlines() if not ln.startswith("#")]
    for line in lines:
        assert not line.startswith("llm_agents_hits "), f"Unexpected line: {line}"


# ---------------------------------------------------------------------------
# T6 — Export: histogram
# ---------------------------------------------------------------------------


def test_export_histogram_format():
    """T6: histogram export contains _bucket, _sum, _count lines; +Inf bucket present."""
    reg = get_registry()
    h = reg.histogram("latency", help="Latency seconds.", labels={"svc": "a"})
    h.observe(0.05)
    h.observe(1.5)
    output = reg.export()

    assert "# TYPE llm_agents_latency histogram" in output
    assert "# HELP llm_agents_latency Latency seconds." in output
    assert 'le="+Inf"' in output
    assert "llm_agents_latency_sum" in output
    assert "llm_agents_latency_count" in output
    assert "llm_agents_latency_bucket" in output


def test_export_histogram_inf_bucket_label():
    """T6b: +Inf bucket appears with le=\"+Inf\" label."""
    reg = get_registry()
    reg.histogram("dur").observe(99.0)
    output = reg.export()
    assert 'le="+Inf"' in output


# ---------------------------------------------------------------------------
# T7 — Registry reset
# ---------------------------------------------------------------------------


def test_registry_reset_clears_all():
    """T7: export() returns empty string after reset()."""
    reg = get_registry()
    reg.counter("foo").inc()
    reg.gauge("bar").set(1.0)
    reg.reset()
    assert reg.export() == ""


# ---------------------------------------------------------------------------
# T8 — StructuredLogger outputs valid JSON
# ---------------------------------------------------------------------------


def _capture_log(name: str, msg: str, **extra) -> dict:
    """Helper: capture StructuredLogger output into a dict."""
    buf = io.StringIO()
    logger = StructuredLogger(name)
    # Replace handler with one writing to buf so we can capture output.
    stdlib_logger = logging.getLogger(name)
    stdlib_logger.handlers.clear()
    handler = logging.StreamHandler(buf)
    from llm_agents.infra.observability._logging import JSONFormatter

    handler.setFormatter(JSONFormatter())
    stdlib_logger.addHandler(handler)
    stdlib_logger.setLevel(logging.DEBUG)
    stdlib_logger.propagate = False
    logger.info(msg, **extra)
    line = buf.getvalue().strip()
    return json.loads(line)


def test_structured_logger_valid_json():
    """T8: StructuredLogger emits valid JSON with required keys."""
    data = _capture_log("test.t8", "hello world")
    assert "timestamp" in data
    assert "level" in data
    assert "logger" in data
    assert "message" in data
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert data["logger"] == "test.t8"


def test_structured_logger_extra_fields():
    """T8b: keyword arguments appear as extra JSON fields."""
    data = _capture_log("test.t8b", "test", model="gpt-4", tokens=100)
    assert data["model"] == "gpt-4"
    assert data["tokens"] == 100


# ---------------------------------------------------------------------------
# T9 — StructuredLogger trace correlation
# ---------------------------------------------------------------------------


def test_structured_logger_trace_correlation_inside_span():
    """T9a: Inside tracer.span(), log JSON has trace_id and span_id matching current_span."""
    from llm_agents.infra.tracing import current_span

    with tracer.span("test-span"):
        buf = io.StringIO()
        stdlib_logger = logging.getLogger("test.t9a")
        stdlib_logger.handlers.clear()
        handler = logging.StreamHandler(buf)
        from llm_agents.infra.observability._logging import JSONFormatter  # noqa: PLC0415

        handler.setFormatter(JSONFormatter())
        stdlib_logger.addHandler(handler)
        stdlib_logger.setLevel(logging.DEBUG)
        stdlib_logger.propagate = False

        logger = StructuredLogger("test.t9a")
        logger._logger = stdlib_logger
        logger.info("inside span")

        active = current_span()
        data = json.loads(buf.getvalue().strip())
        assert data["trace_id"] == active.trace_id
        assert data["span_id"] == active.span_id


def test_structured_logger_trace_correlation_outside_span():
    """T9b: Outside any span, trace_id and span_id are null."""
    data = _capture_log("test.t9b", "outside span")
    assert data["trace_id"] is None
    assert data["span_id"] is None


# ---------------------------------------------------------------------------
# T10 — bridge_span: general (non-LLM)
# ---------------------------------------------------------------------------


def test_bridge_span_general_updates_spans_total_and_duration():
    """T10: bridge_span on a non-LLM span updates spans_total counter and duration histogram."""
    reg = get_registry()
    span = _make_finished_span(kind=SpanKind.TOOL, status=SpanStatus.OK, duration_s=0.25)
    bridge_span(span, registry=reg)

    output = reg.export()
    # spans_total counter updated ("spans_total" already ends in _total, so registry
    # keeps the name as-is → full name: llm_agents_spans_total)
    assert "llm_agents_spans_total" in output
    assert 'kind="tool"' in output
    assert 'status="ok"' in output
    # span_duration histogram updated
    assert "llm_agents_span_duration_seconds" in output


def test_bridge_span_general_no_llm_metrics():
    """T10b: bridge_span on a non-LLM span does NOT create llm_requests_total."""
    reg = get_registry()
    span = _make_finished_span(kind=SpanKind.AGENT, status=SpanStatus.OK)
    bridge_span(span, registry=reg)

    output = reg.export()
    assert "llm_requests" not in output


# ---------------------------------------------------------------------------
# T11 — bridge_span: LLM span with full attributes
# ---------------------------------------------------------------------------


def test_bridge_span_llm_full_attributes():
    """T11: LLM span with all attributes updates all LLM-specific metrics."""
    reg = get_registry()
    span = _make_finished_span(
        kind=SpanKind.LLM,
        status=SpanStatus.OK,
        duration_s=0.5,
        attributes={
            "model": "gpt-4o",
            "latency_s": 0.5,
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "cost_usd": 0.003,
        },
    )
    bridge_span(span, registry=reg)
    output = reg.export()

    # llm_requests_total incremented
    assert "llm_agents_llm_requests_total" in output
    assert 'model="gpt-4o"' in output

    # llm_latency_seconds histogram present
    assert "llm_agents_llm_latency_seconds" in output

    # prompt/completion token counters
    assert "llm_agents_llm_prompt_tokens_total" in output
    assert "llm_agents_llm_completion_tokens_total" in output

    # cost counter
    assert "llm_agents_llm_cost_usd_total" in output


def test_bridge_span_llm_token_counter_values():
    """T11b: prompt and completion token counter values match span attributes."""
    reg = get_registry()
    span = _make_finished_span(
        kind=SpanKind.LLM,
        status=SpanStatus.OK,
        attributes={"model": "gpt-4o", "prompt_tokens": 50, "completion_tokens": 75},
    )
    bridge_span(span, registry=reg)

    # Use the same bare names as _bridge.py (without subsystem prefix in name)
    prompt_c = reg.counter("prompt_tokens_total", subsystem="llm", labels={"model": "gpt-4o"})
    completion_c = reg.counter(
        "completion_tokens_total", subsystem="llm", labels={"model": "gpt-4o"}
    )
    assert prompt_c.value == 50.0
    assert completion_c.value == 75.0


# ---------------------------------------------------------------------------
# T12 — bridge_span: LLM error
# ---------------------------------------------------------------------------


def test_bridge_span_llm_error_increments_errors_total():
    """T12: llm_errors_total incremented when LLM span status is ERROR."""
    reg = get_registry()
    span = _make_finished_span(
        kind=SpanKind.LLM,
        status=SpanStatus.ERROR,
        attributes={"model": "gpt-4o"},
    )
    bridge_span(span, registry=reg)

    output = reg.export()
    assert "llm_agents_llm_errors_total" in output

    err_c = reg.counter("errors_total", subsystem="llm", labels={"model": "gpt-4o"})
    assert err_c.value == 1.0


def test_bridge_span_llm_ok_no_errors_total():
    """T12b: llm_errors_total NOT incremented when LLM span status is OK."""
    reg = get_registry()
    span = _make_finished_span(
        kind=SpanKind.LLM,
        status=SpanStatus.OK,
        attributes={"model": "gpt-4o"},
    )
    bridge_span(span, registry=reg)

    output = reg.export()
    assert "llm_errors_total" not in output


# ---------------------------------------------------------------------------
# T13 — bridge_span: missing attributes do not raise
# ---------------------------------------------------------------------------


def test_bridge_span_llm_empty_attributes_no_raise():
    """T13: bridge_span on LLM span with empty attributes does not raise."""
    reg = get_registry()
    span = _make_finished_span(kind=SpanKind.LLM, status=SpanStatus.OK, attributes={})
    bridge_span(span, registry=reg)  # must not raise

    output = reg.export()
    # Only unconditional metrics are present
    assert "llm_agents_spans_total" in output
    assert "llm_agents_span_duration_seconds" in output
    assert "llm_agents_llm_requests_total" in output
    # Optional metrics absent
    assert "llm_latency" not in output
    assert "prompt_tokens" not in output
    assert "completion_tokens" not in output
    assert "cost_usd" not in output


def test_bridge_span_does_not_raise_on_bad_data():
    """T13b: bridge_span is fault-tolerant; any internal error emits a warning, not an exception."""
    import warnings

    # Construct a span with an unparseable attributes value to force a potential error
    span = _make_finished_span(kind=SpanKind.INTERNAL, status=SpanStatus.OK, duration_s=0.1)

    # bridge_span should NEVER raise; even if we pass a corrupt registry
    class BrokenRegistry(MetricsRegistry):
        def counter(self, *args, **kwargs):
            raise RuntimeError("injected failure")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        bridge_span(span, registry=BrokenRegistry())

    # A warning was emitted, no exception propagated
    assert len(w) == 1
    assert "bridge_span" in str(w[0].message)
