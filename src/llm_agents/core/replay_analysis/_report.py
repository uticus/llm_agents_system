"""Data models for trace analysis reports.

:class:`SpanSummary` is a lightweight per-span entry used in timelines and
replay output.  :class:`AnalysisReport` aggregates span-level data into an
overview of a single :class:`Trace`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm_agents.infra.tracing._models import SpanKind, SpanStatus


@dataclass(frozen=True)
class SpanSummary:
    """Lightweight record of a single span for timeline and replay use.

    Args:
        name:       Span name.
        kind:       Semantic kind of the span.
        duration_s: Wall-clock duration in seconds.
        status:     Terminal status of the span.
    """

    name: str
    kind: SpanKind
    duration_s: float
    status: SpanStatus


@dataclass
class AnalysisReport:
    """Structured analysis of a recorded :class:`Trace`.

    Args:
        trace_id:              Identifier of the analyzed trace.
        span_count:            Total number of finished spans.
        llm_call_count:        Number of :attr:`SpanKind.LLM` spans.
        tool_call_count:       Number of :attr:`SpanKind.TOOL` spans.
        error_count:           Number of spans with :attr:`SpanStatus.ERROR`.
        total_duration_s:      Wall-clock span of the trace (latest end_time
                               minus earliest start_time across all spans).
        total_prompt_tokens:   Sum of ``prompt_tokens`` attributes across all
                               LLM spans.
        total_completion_tokens: Sum of ``completion_tokens`` attributes across
                               all LLM spans.
        total_cost_usd:        Sum of ``cost_usd`` attributes across all
                               LLM spans.
        timeline:              One :class:`SpanSummary` per span in the trace,
                               ordered by ``start_time``.
        errors:                Human-readable descriptions of error spans (name
                               plus the ``error`` attribute when present).
    """

    trace_id: str
    span_count: int = 0
    llm_call_count: int = 0
    tool_call_count: int = 0
    error_count: int = 0
    total_duration_s: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    timeline: list[SpanSummary] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
