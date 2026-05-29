"""Data models for the evaluation framework.

:class:`EvalCase` describes one evaluation input/expected-output pair.
:class:`EvalResult` holds the outcome of running an agent on one case.
:class:`EvalReport` aggregates results across a full evaluation run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalCase:
    """A single evaluation input/expected-output pair.

    Args:
        input:           The input string passed to the agent.
        expected_output: The expected output to compare against.
        metadata:        Arbitrary key-value metadata (tags, labels, etc.).
        case_id:         Optional identifier.  Defaults to an empty string.
    """

    input: str
    expected_output: str
    metadata: dict[str, Any] = field(default_factory=dict)
    case_id: str = ""


@dataclass
class EvalResult:
    """Outcome of running an agent on a single :class:`EvalCase`.

    Args:
        case:          The :class:`EvalCase` that was evaluated.
        actual_output: The string produced by the agent.
        score:         Numeric score in [0.0, 1.0] from the scorer.
        latency_s:     Wall-clock time taken by the agent call in seconds.
        success:       ``True`` when the score meets the passing threshold.
        run_index:     Index of the repeat run (0-based).
        error:         Error message if the agent raised an exception.
    """

    case: EvalCase
    actual_output: str
    score: float
    latency_s: float
    success: bool = True
    run_index: int = 0
    error: str | None = None


@dataclass
class EvalReport:
    """Aggregated statistics across a set of :class:`EvalResult` objects.

    Args:
        total_cases:   Number of unique cases evaluated.
        total_runs:    Total number of individual runs (cases * repeats).
        mean_score:    Mean score across all runs.
        min_score:     Minimum score across all runs.
        max_score:     Maximum score across all runs.
        std_score:     Sample standard deviation of scores (0.0 if only one run).
        pass_rate:     Fraction of runs where score >= threshold.
        threshold:     The passing threshold used to compute ``pass_rate``.
        results:       All individual :class:`EvalResult` objects.
    """

    total_cases: int = 0
    total_runs: int = 0
    mean_score: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    std_score: float = 0.0
    pass_rate: float = 0.0
    threshold: float = 0.5
    results: list[EvalResult] = field(default_factory=list)
