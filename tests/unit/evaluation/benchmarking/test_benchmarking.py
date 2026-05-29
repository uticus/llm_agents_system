"""Unit tests for evaluation/benchmarking.

Covers BenchmarkTask/Suite/TaskResult/BenchmarkReport models,
BenchmarkRunner execution (success, failure, metadata extraction),
aggregated metric computation, percentile, and CLI smoke test.
No real network calls.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys

import pytest

from llm_agents.evaluation.benchmarking import (
    BenchmarkReport,
    BenchmarkRunner,
    BenchmarkTask,
    Suite,
    TaskResult,
)
from llm_agents.evaluation.benchmarking._runner import _percentile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _task(task_id: str, input_text: str, expected: str) -> BenchmarkTask:
    return BenchmarkTask(task_id=task_id, input=input_text, expected_output=expected)


def _suite(*pairs: tuple[str, str]) -> Suite:
    tasks = [_task(f"t{i}", inp, exp) for i, (inp, exp) in enumerate(pairs)]
    return Suite(name="test-suite", tasks=tasks)


async def _echo_agent(text: str) -> str:
    return text


async def _wrong_agent(text: str) -> str:
    return "wrong"


async def _raise_agent(text: str) -> str:
    raise RuntimeError("crash")


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_benchmark_task_defaults():
    """BenchmarkTask stores fields with empty metadata."""
    t = _task("t1", "hello", "world")
    assert t.task_id == "t1"
    assert t.metadata == {}


def test_suite_defaults():
    """Suite initialises with empty task list."""
    s = Suite(name="s")
    assert s.tasks == []


def test_task_result_defaults():
    """TaskResult defaults all numeric fields to 0."""
    r = TaskResult(task_id="t1", success=True)
    assert r.prompt_tokens == 0
    assert r.cost_usd == 0.0
    assert r.cache_hit is False
    assert r.error is None


def test_benchmark_report_defaults():
    """BenchmarkReport initialises with empty results and zero metrics."""
    r = BenchmarkReport(suite_name="s")
    assert r.task_results == []
    assert r.success_rate == 0.0


# ---------------------------------------------------------------------------
# T1: BenchmarkRunner — success path
# ---------------------------------------------------------------------------


def test_runner_echo_agent_all_pass():
    """T1: Echo agent passes all tasks (exact match scorer)."""
    suite = _suite(("a", "a"), ("b", "b"), ("c", "c"))
    runner = BenchmarkRunner(agent_fn=_echo_agent)
    report = asyncio.run(runner.run(suite))
    assert report.success_rate == pytest.approx(1.0)
    assert len(report.task_results) == 3
    assert all(r.success for r in report.task_results)


def test_runner_wrong_agent_all_fail():
    """T1b: Agent returning wrong output produces success_rate=0.0."""
    suite = _suite(("hello", "expected"), ("world", "other"))
    runner = BenchmarkRunner(agent_fn=_wrong_agent)
    report = asyncio.run(runner.run(suite))
    assert report.success_rate == pytest.approx(0.0)
    assert all(not r.success for r in report.task_results)


def test_runner_partial_success():
    """T1c: Mixed results yield correct success_rate."""
    call_count = [0]

    async def alternating_agent(text: str) -> str:
        call_count[0] += 1
        if call_count[0] % 2 == 1:
            return text  # success on odd calls
        return "wrong"  # failure on even calls

    suite = _suite(("a", "a"), ("b", "b"), ("c", "c"), ("d", "d"))
    runner = BenchmarkRunner(agent_fn=alternating_agent)
    report = asyncio.run(runner.run(suite))
    assert report.success_rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# T2: BenchmarkRunner — failure and exception handling
# ---------------------------------------------------------------------------


def test_runner_captures_exception():
    """T2: Agent exceptions are captured in TaskResult.error; task marked failed."""
    suite = _suite(("q", "a"))
    runner = BenchmarkRunner(agent_fn=_raise_agent)
    report = asyncio.run(runner.run(suite))
    assert report.success_rate == pytest.approx(0.0)
    assert report.task_results[0].error is not None
    assert "RuntimeError" in report.task_results[0].error


def test_runner_empty_suite():
    """T2b: Empty suite produces a report with zero tasks."""
    suite = Suite(name="empty")
    runner = BenchmarkRunner(agent_fn=_echo_agent)
    report = asyncio.run(runner.run(suite))
    assert report.task_results == []
    assert report.success_rate == 0.0


# ---------------------------------------------------------------------------
# T3: AgentOutput object support
# ---------------------------------------------------------------------------


def test_runner_agent_output_object():
    """T3: Runner extracts metadata from AgentOutput-compatible objects."""

    class AgentOutput:
        def __init__(self):
            self.output = "answer"
            self.prompt_tokens = 100
            self.completion_tokens = 50
            self.cost_usd = 0.002
            self.cache_hit = True

    async def structured_agent(text: str) -> AgentOutput:
        return AgentOutput()

    suite = _suite(("q", "answer"))
    runner = BenchmarkRunner(agent_fn=structured_agent)
    report = asyncio.run(runner.run(suite))
    r = report.task_results[0]
    assert r.success is True
    assert r.prompt_tokens == 100
    assert r.completion_tokens == 50
    assert r.cost_usd == pytest.approx(0.002)
    assert r.cache_hit is True


def test_runner_cache_hit_rate():
    """T3b: cache_hit_rate is computed correctly."""

    class HitOutput:
        output = "x"
        prompt_tokens = 0
        completion_tokens = 0
        cost_usd = 0.0
        cache_hit = True

    class MissOutput:
        output = "x"
        prompt_tokens = 0
        completion_tokens = 0
        cost_usd = 0.0
        cache_hit = False

    call_n = [0]

    async def cached_agent(text: str):
        call_n[0] += 1
        return HitOutput() if call_n[0] % 2 == 1 else MissOutput()

    suite = _suite(("x", "x"), ("x", "x"))
    runner = BenchmarkRunner(agent_fn=cached_agent)
    report = asyncio.run(runner.run(suite))
    assert report.cache_hit_rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# T4: custom scorer
# ---------------------------------------------------------------------------


def test_runner_custom_scorer():
    """T4: BenchmarkRunner accepts a custom scorer callable."""

    async def agent(text: str) -> str:
        return text.upper()

    # Scorer: case-insensitive contains check
    def ci_scorer(expected: str, actual: str) -> bool:
        return expected.lower() in actual.lower()

    suite = _suite(("hello", "hello"))
    runner = BenchmarkRunner(agent_fn=agent, scorer=ci_scorer)
    report = asyncio.run(runner.run(suite))
    assert report.success_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T5: metric aggregation
# ---------------------------------------------------------------------------


def test_report_mean_tokens():
    """T5: mean_tokens equals (prompt + completion) summed and averaged."""
    call_n = [0]

    class TokenOutput:
        def __init__(self, p, c):
            self.output = "x"
            self.prompt_tokens = p
            self.completion_tokens = c
            self.cost_usd = 0.0
            self.cache_hit = False

    async def tokenized_agent(text: str):
        call_n[0] += 1
        return TokenOutput(10 * call_n[0], 5 * call_n[0])

    suite = _suite(("a", "a"), ("b", "b"))
    runner = BenchmarkRunner(agent_fn=tokenized_agent)
    report = asyncio.run(runner.run(suite))
    # call 1: 10 + 5 = 15; call 2: 20 + 10 = 30; mean = 22.5
    assert report.mean_tokens == pytest.approx(22.5)


# ---------------------------------------------------------------------------
# T6: _percentile helper
# ---------------------------------------------------------------------------


def test_percentile_median():
    """T6: _percentile returns the 50th percentile (median) correctly."""
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    # 50th percentile of 5 values: rank = ceil(0.5*5) - 1 = 2 → value 3.0
    assert _percentile(data, 50) == pytest.approx(3.0)


def test_percentile_max():
    """T6b: 100th percentile returns the maximum."""
    data = [1.0, 2.0, 3.0]
    assert _percentile(data, 100) == pytest.approx(3.0)


def test_percentile_empty():
    """T6c: Empty list returns 0.0."""
    assert _percentile([], 95) == 0.0


def test_percentile_single():
    """T6d: Single-element list returns that element for any percentile."""
    assert _percentile([42.0], 95) == pytest.approx(42.0)


# ---------------------------------------------------------------------------
# T7: CLI smoke test
# ---------------------------------------------------------------------------


def test_cli_tiny_suite():
    """T7: CLI runs the tiny suite and prints valid JSON."""
    result = subprocess.run(
        [sys.executable, "-m", "llm_agents.evaluation.benchmarking", "--suite", "tiny"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["suite_name"] == "tiny"
    assert data["success_rate"] == pytest.approx(1.0)
    assert data["total_tasks"] == 3


def test_cli_help():
    """T7b: CLI --help exits with code 0."""
    result = subprocess.run(
        [sys.executable, "-m", "llm_agents.evaluation.benchmarking", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "suite" in result.stdout.lower()
