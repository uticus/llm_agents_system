"""Data models for the benchmarking subsystem.

:class:`BenchmarkTask` — a single task with expected outcome.
:class:`Suite` — a named collection of tasks.
:class:`TaskResult` — execution outcome for one task.
:class:`BenchmarkReport` — aggregated metrics for a suite run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchmarkTask:
    """A single benchmark task.

    Args:
        task_id:         Unique task identifier.
        input:           Input string passed to the agent.
        expected_output: Reference output for scoring.
        metadata:        Arbitrary key-value metadata.
    """

    task_id: str
    input: str
    expected_output: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Suite:
    """A named collection of :class:`BenchmarkTask` objects.

    Args:
        name:  Suite identifier (e.g. ``"tiny"``, ``"gsm8k"``).
        tasks: Ordered list of tasks to execute.
    """

    name: str
    tasks: list[BenchmarkTask] = field(default_factory=list)


@dataclass
class TaskResult:
    """Execution outcome for one :class:`BenchmarkTask`.

    Args:
        task_id:           Echoes :attr:`BenchmarkTask.task_id`.
        success:           Whether the agent output matched the expected output.
        prompt_tokens:     Prompt tokens consumed (0 if unavailable).
        completion_tokens: Completion tokens generated (0 if unavailable).
        latency_s:         Wall-clock execution time in seconds.
        cost_usd:          Estimated cost in USD (0.0 if unavailable).
        cache_hit:         Whether the response came from a cache layer.
        actual_output:     The agent-produced output string.
        error:             Error message if the agent raised an exception.
    """

    task_id: str
    success: bool
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0
    cache_hit: bool = False
    actual_output: str = ""
    error: str | None = None


@dataclass
class BenchmarkReport:
    """Aggregated metrics for a complete suite run.

    Args:
        suite_name:      Name of the suite that was run.
        task_results:    One :class:`TaskResult` per task.
        success_rate:    Fraction of tasks that succeeded (0.0 – 1.0).
        mean_tokens:     Mean total tokens per task (prompt + completion).
        mean_latency_s:  Mean wall-clock latency per task.
        p95_latency_s:   95th-percentile latency (0.0 if fewer than 20 tasks).
        mean_cost_usd:   Mean cost per task in USD.
        cache_hit_rate:  Fraction of tasks served from cache.
    """

    suite_name: str
    task_results: list[TaskResult] = field(default_factory=list)
    success_rate: float = 0.0
    mean_tokens: float = 0.0
    mean_latency_s: float = 0.0
    p95_latency_s: float = 0.0
    mean_cost_usd: float = 0.0
    cache_hit_rate: float = 0.0
