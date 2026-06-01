"""Unit tests for evaluation/framework.

Covers EvalCase/EvalResult/EvalReport models, built-in metrics,
EvalHarness (single run and repeat), and aggregate() statistics.
No real network calls — agent callable is a stub.
"""

from __future__ import annotations

import asyncio

import pytest

from llm_agents.evaluation.framework import (
    ContainsMetric,
    EvalCase,
    EvalHarness,
    EvalReport,
    EvalResult,
    ExactMatchMetric,
    Metric,
    NormalizedMatchMetric,
    aggregate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_case(
    input_text: str = "what is 2+2?",
    expected: str = "4",
    case_id: str = "",
) -> EvalCase:
    return EvalCase(input=input_text, expected_output=expected, case_id=case_id)


async def _echo_agent(text: str) -> str:
    """Agent that echoes its input as output."""
    return text


async def _fixed_agent(response: str):
    async def _fn(text: str) -> str:
        return response

    return _fn


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_eval_case_defaults():
    """EvalCase stores input, expected_output, and has empty defaults."""
    case = _make_case("hello", "world")
    assert case.input == "hello"
    assert case.expected_output == "world"
    assert case.metadata == {}
    assert case.case_id == ""


def test_eval_result_defaults():
    """EvalResult stores all fields correctly."""
    case = _make_case()
    r = EvalResult(case=case, actual_output="4", score=1.0, latency_s=0.01)
    assert r.success is True
    assert r.run_index == 0
    assert r.error is None


def test_eval_report_defaults():
    """EvalReport defaults to zero totals."""
    r = EvalReport()
    assert r.total_cases == 0
    assert r.mean_score == 0.0
    assert r.results == []


# ---------------------------------------------------------------------------
# T1: Metric protocol and built-in metrics
# ---------------------------------------------------------------------------


def test_exact_match_metric_correct():
    """T1: ExactMatchMetric returns 1.0 on exact match."""
    m = ExactMatchMetric()
    assert m.score("hello", "hello") == 1.0


def test_exact_match_metric_wrong():
    """T1b: ExactMatchMetric returns 0.0 on mismatch."""
    m = ExactMatchMetric()
    assert m.score("hello", "world") == 0.0


def test_exact_match_metric_case_sensitive():
    """T1c: ExactMatchMetric is case-sensitive."""
    m = ExactMatchMetric()
    assert m.score("Hello", "hello") == 0.0


def test_contains_metric_found():
    """T1d: ContainsMetric returns 1.0 when expected is substring of actual."""
    m = ContainsMetric()
    assert m.score("answer", "The answer is here") == 1.0


def test_contains_metric_not_found():
    """T1e: ContainsMetric returns 0.0 when expected not in actual."""
    m = ContainsMetric()
    assert m.score("missing", "The answer is here") == 0.0


def test_contains_metric_case_insensitive():
    """T1f: ContainsMetric is case-insensitive."""
    m = ContainsMetric()
    assert m.score("ANSWER", "the answer is here") == 1.0


def test_normalized_match_metric():
    """T1g: NormalizedMatchMetric strips whitespace and lowercases."""
    m = NormalizedMatchMetric()
    assert m.score("Hello", "  hello  ") == 1.0
    assert m.score("Hello", "world") == 0.0


def test_metric_protocol_satisfied():
    """T1h: Built-in metrics satisfy the Metric protocol at runtime."""
    assert isinstance(ExactMatchMetric(), Metric)
    assert isinstance(ContainsMetric(), Metric)
    assert isinstance(NormalizedMatchMetric(), Metric)


# ---------------------------------------------------------------------------
# T2: EvalHarness — single run
# ---------------------------------------------------------------------------


def test_harness_run_single_case_exact_match():
    """T2: Harness runs agent on one case; exact match score = 1.0."""

    async def agent(text: str) -> str:
        return text  # echo

    case = _make_case("hello", "hello")
    harness = EvalHarness(agent_fn=agent, metric=ExactMatchMetric())
    results = asyncio.run(harness.run([case]))
    assert len(results) == 1
    assert results[0].score == pytest.approx(1.0)
    assert results[0].success is True


def test_harness_run_single_case_no_match():
    """T2b: Harness records score=0.0 when agent output does not match."""

    async def agent(text: str) -> str:
        return "wrong"

    case = _make_case("hello", "expected")
    harness = EvalHarness(agent_fn=agent, metric=ExactMatchMetric())
    results = asyncio.run(harness.run([case]))
    assert results[0].score == pytest.approx(0.0)
    assert results[0].success is False


def test_harness_run_multiple_cases():
    """T2c: Harness runs agent on multiple cases; returns one result per case."""

    async def agent(text: str) -> str:
        return text

    cases = [_make_case(f"q{i}", f"q{i}") for i in range(5)]
    harness = EvalHarness(agent_fn=agent, metric=ExactMatchMetric())
    results = asyncio.run(harness.run(cases))
    assert len(results) == 5
    assert all(r.score == pytest.approx(1.0) for r in results)


def test_harness_captures_agent_exception():
    """T2d: Harness captures agent exceptions; result has error, score=0.0."""

    async def boom(text: str) -> str:
        raise RuntimeError("crash")

    case = _make_case()
    harness = EvalHarness(agent_fn=boom, metric=ExactMatchMetric())
    results = asyncio.run(harness.run([case]))
    assert results[0].error is not None
    assert "RuntimeError" in results[0].error
    assert results[0].score == pytest.approx(0.0)
    assert results[0].success is False


# ---------------------------------------------------------------------------
# T3: EvalHarness — repeated runs
# ---------------------------------------------------------------------------


def test_harness_repeat_produces_multiple_results():
    """T3: repeat=3 produces 3 results per case."""

    async def agent(text: str) -> str:
        return text

    cases = [_make_case("x", "x")]
    harness = EvalHarness(agent_fn=agent, metric=ExactMatchMetric())
    results = asyncio.run(harness.run(cases, repeat=3))
    assert len(results) == 3


def test_harness_repeat_indices():
    """T3b: Repeated results have ascending run_index values."""

    async def agent(text: str) -> str:
        return text

    cases = [_make_case("x", "x")]
    harness = EvalHarness(agent_fn=agent, metric=ExactMatchMetric())
    results = asyncio.run(harness.run(cases, repeat=3))
    assert [r.run_index for r in results] == [0, 1, 2]


def test_harness_empty_cases():
    """T3c: Running on empty case list returns empty results."""

    async def agent(text: str) -> str:
        return text

    harness = EvalHarness(agent_fn=agent, metric=ExactMatchMetric())
    results = asyncio.run(harness.run([]))
    assert results == []


# ---------------------------------------------------------------------------
# T4: aggregate()
# ---------------------------------------------------------------------------


def test_aggregate_empty():
    """T4: aggregate() on empty list returns zero-valued report."""
    report = aggregate([])
    assert report.total_runs == 0
    assert report.mean_score == 0.0


def test_aggregate_all_pass():
    """T4b: aggregate() with all score=1.0 gives mean=1.0 and pass_rate=1.0."""
    case = _make_case()
    results = [
        EvalResult(case=case, actual_output="ok", score=1.0, latency_s=0.0) for _ in range(4)
    ]
    report = aggregate(results)
    assert report.mean_score == pytest.approx(1.0)
    assert report.pass_rate == pytest.approx(1.0)
    assert report.min_score == pytest.approx(1.0)
    assert report.max_score == pytest.approx(1.0)
    assert report.std_score == pytest.approx(0.0)


def test_aggregate_all_fail():
    """T4c: aggregate() with all score=0.0 gives pass_rate=0.0."""
    case = _make_case()
    results = [EvalResult(case=case, actual_output="", score=0.0, latency_s=0.0) for _ in range(3)]
    report = aggregate(results)
    assert report.pass_rate == pytest.approx(0.0)
    assert report.mean_score == pytest.approx(0.0)


def test_aggregate_mixed_scores():
    """T4d: aggregate() computes correct mean, min, max, std for mixed scores."""
    case = _make_case()
    scores = [0.0, 0.5, 1.0]
    results = [EvalResult(case=case, actual_output="", score=s, latency_s=0.0) for s in scores]
    report = aggregate(results, threshold=0.5)
    assert report.mean_score == pytest.approx(0.5)
    assert report.min_score == pytest.approx(0.0)
    assert report.max_score == pytest.approx(1.0)
    # pass: 0.5 >= 0.5 and 1.0 >= 0.5 → 2/3
    assert report.pass_rate == pytest.approx(2 / 3)
    # std of [0, 0.5, 1.0]
    import statistics

    expected_std = statistics.stdev([0.0, 0.5, 1.0])
    assert report.std_score == pytest.approx(expected_std)


def test_aggregate_total_runs():
    """T4e: aggregate() reports correct total_runs."""
    case = _make_case()
    results = [
        EvalResult(case=case, actual_output="ok", score=1.0, latency_s=0.0) for _ in range(6)
    ]
    report = aggregate(results)
    assert report.total_runs == 6


def test_aggregate_custom_threshold():
    """T4f: aggregate() respects a custom threshold for pass_rate."""
    case = _make_case()
    results = [EvalResult(case=case, actual_output="ok", score=0.7, latency_s=0.0)]
    # threshold=0.5: score 0.7 passes
    report_low = aggregate(results, threshold=0.5)
    assert report_low.pass_rate == pytest.approx(1.0)
    # threshold=0.8: score 0.7 fails
    report_high = aggregate(results, threshold=0.8)
    assert report_high.pass_rate == pytest.approx(0.0)
