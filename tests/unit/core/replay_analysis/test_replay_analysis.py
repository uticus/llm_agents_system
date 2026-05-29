"""Unit tests for core/replay_analysis.

Covers trace loading, analysis (counts, totals, timeline, errors), replay
engine (deterministic, no provider calls), and divergence detection.
All tests use committed fixture files; no real network calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_agents.core.replay_analysis import (
    ReplayEngine,
    SpanSummary,
    analyze,
    detect_divergence,
    load_trace,
)
from llm_agents.infra.tracing._models import FinishedSpan, SpanKind, SpanStatus, Trace
from llm_agents.infra.tracing._serialization import serialize_trace

# ---------------------------------------------------------------------------
# Paths to fixture files
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parents[3] / "fixtures" / "traces"
TRACE_OK = FIXTURES / "trace_ok.json"
TRACE_ERR = FIXTURES / "trace_error.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_span(
    name: str,
    kind: SpanKind,
    status: SpanStatus,
    start: float,
    duration: float,
    **attrs: object,
) -> FinishedSpan:
    return FinishedSpan(
        trace_id="t1",
        span_id=name,
        parent_id=None,
        name=name,
        kind=kind,
        start_time=start,
        start_wall="2026-01-01T00:00:00+00:00",
        end_time=start + duration,
        duration_s=duration,
        status=status,
        attributes=dict(attrs),
    )


def _make_trace(*spans: FinishedSpan) -> Trace:
    return Trace(trace_id="t1", spans=spans)


# ---------------------------------------------------------------------------
# T1: load_trace
# ---------------------------------------------------------------------------


def test_load_trace_ok_fixture():
    """T1: load_trace() reads the ok fixture and returns a Trace."""
    trace = load_trace(TRACE_OK)
    assert trace.trace_id == "test-trace-ok-001"
    assert len(trace.spans) == 3


def test_load_trace_error_fixture():
    """T1b: load_trace() reads the error fixture and returns a Trace."""
    trace = load_trace(TRACE_ERR)
    assert trace.trace_id == "test-trace-err-001"
    assert len(trace.spans) == 2


def test_load_trace_missing_file_raises():
    """T1c: load_trace() raises FileNotFoundError for a missing file."""
    with pytest.raises(FileNotFoundError):
        load_trace(FIXTURES / "nonexistent.json")


def test_load_trace_invalid_json_raises(tmp_path: Path):
    """T1d: load_trace() raises json.JSONDecodeError for non-JSON content."""
    import json

    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not valid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_trace(bad_file)


def test_load_trace_roundtrip(tmp_path: Path):
    """T1e: serialize then load produces an identical Trace."""
    original = load_trace(TRACE_OK)
    serialized = serialize_trace(original)
    out_path = tmp_path / "rt.json"
    out_path.write_text(json.dumps(serialized), encoding="utf-8")
    reloaded = load_trace(out_path)
    assert reloaded.trace_id == original.trace_id
    assert len(reloaded.spans) == len(original.spans)


# ---------------------------------------------------------------------------
# T2: analyze()
# ---------------------------------------------------------------------------


def test_analyze_ok_trace_span_counts():
    """T2: analyze() counts spans, LLM calls, and tool calls correctly."""
    trace = load_trace(TRACE_OK)
    report = analyze(trace)
    assert report.trace_id == "test-trace-ok-001"
    assert report.span_count == 3
    assert report.llm_call_count == 1
    assert report.tool_call_count == 1
    assert report.error_count == 0


def test_analyze_ok_trace_tokens_and_cost():
    """T2b: analyze() sums prompt_tokens, completion_tokens, cost_usd from LLM spans."""
    trace = load_trace(TRACE_OK)
    report = analyze(trace)
    assert report.total_prompt_tokens == 100
    assert report.total_completion_tokens == 50
    assert pytest.approx(report.total_cost_usd, abs=1e-6) == 0.001


def test_analyze_ok_trace_total_duration():
    """T2c: analyze() computes total_duration_s as latest_end - earliest_start."""
    trace = load_trace(TRACE_OK)
    report = analyze(trace)
    # earliest start = 0.0, latest end = 0.5 (routing span)
    assert pytest.approx(report.total_duration_s, abs=1e-6) == 0.5


def test_analyze_ok_trace_timeline_ordered():
    """T2d: analyze() timeline is sorted by start_time."""
    trace = load_trace(TRACE_OK)
    report = analyze(trace)
    assert len(report.timeline) == 3
    # routing at 0.0, llm_call at 0.1, tool:add at 0.41
    assert report.timeline[0].name == "routing"
    assert report.timeline[1].name == "llm_call"
    assert report.timeline[2].name == "tool:add"


def test_analyze_error_trace_counts():
    """T2e: analyze() counts error spans and populates the errors list."""
    trace = load_trace(TRACE_ERR)
    report = analyze(trace)
    assert report.error_count == 2
    assert len(report.errors) == 2
    assert any("Rate limit" in e for e in report.errors)


def test_analyze_empty_trace():
    """T2f: analyze() handles an empty trace gracefully."""
    trace = Trace(trace_id="empty", spans=())
    report = analyze(trace)
    assert report.span_count == 0
    assert report.total_duration_s == 0.0
    assert report.timeline == []


def test_analyze_no_llm_spans():
    """T2g: analyze() handles traces with no LLM spans (zero token totals)."""
    span = _make_span("tool:noop", SpanKind.TOOL, SpanStatus.OK, 0.0, 0.01)
    trace = _make_trace(span)
    report = analyze(trace)
    assert report.llm_call_count == 0
    assert report.total_prompt_tokens == 0
    assert report.total_cost_usd == 0.0


# ---------------------------------------------------------------------------
# T3: ReplayEngine
# ---------------------------------------------------------------------------


def test_replay_returns_span_summaries():
    """T3: ReplayEngine.replay() returns one SpanSummary per span."""
    trace = load_trace(TRACE_OK)
    engine = ReplayEngine(trace)
    summaries = engine.replay()
    assert len(summaries) == 3
    assert all(isinstance(s, SpanSummary) for s in summaries)


def test_replay_summaries_ordered_by_start():
    """T3b: ReplayEngine.replay() returns summaries in start_time order."""
    trace = load_trace(TRACE_OK)
    engine = ReplayEngine(trace)
    summaries = engine.replay()
    # routing at 0.0, llm_call at 0.1, tool:add at 0.41
    assert summaries[0].name == "routing"
    assert summaries[1].name == "llm_call"
    assert summaries[2].name == "tool:add"


def test_replay_is_deterministic():
    """T3c: Calling replay() twice on the same engine returns identical results."""
    trace = load_trace(TRACE_OK)
    engine = ReplayEngine(trace)
    first = engine.replay()
    second = engine.replay()
    assert first == second


def test_replay_error_trace_preserves_status():
    """T3d: ReplayEngine preserves ERROR status from the recorded trace."""
    trace = load_trace(TRACE_ERR)
    engine = ReplayEngine(trace)
    summaries = engine.replay()
    assert all(s.status == SpanStatus.ERROR for s in summaries)


def test_replay_engine_exposes_trace():
    """T3e: ReplayEngine.trace returns the original Trace object."""
    trace = load_trace(TRACE_OK)
    engine = ReplayEngine(trace)
    assert engine.trace is trace


# ---------------------------------------------------------------------------
# T4: detect_divergence()
# ---------------------------------------------------------------------------


def test_no_divergence_identical_traces():
    """T4: detect_divergence() returns empty list for identical traces."""
    trace = load_trace(TRACE_OK)
    issues = detect_divergence(trace, trace)
    assert issues == []


def test_divergence_span_count():
    """T4b: detect_divergence() detects a span count mismatch."""
    rec = _make_trace(
        _make_span("a", SpanKind.LLM, SpanStatus.OK, 0.0, 0.1),
        _make_span("b", SpanKind.TOOL, SpanStatus.OK, 0.1, 0.1),
    )
    fresh = _make_trace(
        _make_span("a", SpanKind.LLM, SpanStatus.OK, 0.0, 0.1),
    )
    issues = detect_divergence(rec, fresh)
    assert any("count" in i.lower() for i in issues)


def test_divergence_span_names():
    """T4c: detect_divergence() detects a span name sequence mismatch."""
    rec = _make_trace(
        _make_span("call_a", SpanKind.LLM, SpanStatus.OK, 0.0, 0.1),
    )
    fresh = _make_trace(
        _make_span("call_b", SpanKind.LLM, SpanStatus.OK, 0.0, 0.1),
    )
    issues = detect_divergence(rec, fresh)
    assert any("name" in i.lower() or "sequence" in i.lower() for i in issues)


def test_divergence_status_change():
    """T4d: detect_divergence() detects a per-span status change."""
    rec = _make_trace(
        _make_span("llm_call", SpanKind.LLM, SpanStatus.OK, 0.0, 0.1),
    )
    fresh = _make_trace(
        _make_span("llm_call", SpanKind.LLM, SpanStatus.ERROR, 0.0, 0.1),
    )
    issues = detect_divergence(rec, fresh)
    assert any("status" in i.lower() for i in issues)


def test_divergence_error_recovered():
    """T4e: detect_divergence() flags when a recorded ERROR span is OK in fresh run."""
    rec = _make_trace(
        _make_span("llm_call", SpanKind.LLM, SpanStatus.ERROR, 0.0, 0.1),
    )
    fresh = _make_trace(
        _make_span("llm_call", SpanKind.LLM, SpanStatus.OK, 0.0, 0.1),
    )
    issues = detect_divergence(rec, fresh)
    assert any("ERROR" in i for i in issues)
