"""Trace analyzer: produce a structured :class:`AnalysisReport` from a :class:`Trace`.

:func:`analyze` scans all :class:`FinishedSpan` objects in a :class:`Trace`,
aggregates timing, cost, and token metrics, and builds an
:class:`AnalysisReport` with a timeline and error list.
"""

from __future__ import annotations

from llm_agents.core.replay_analysis._report import AnalysisReport, SpanSummary
from llm_agents.infra.tracing._models import SpanKind, SpanStatus, Trace


def analyze(trace: Trace) -> AnalysisReport:
    """Produce an :class:`AnalysisReport` from *trace*.

    Args:
        trace: A recorded :class:`Trace` (may have been loaded with
               :func:`~llm_agents.core.replay_analysis._loader.load_trace`).

    Returns:
        :class:`AnalysisReport` with per-span timeline, token/cost totals,
        and a list of error descriptions.
    """
    spans = list(trace.spans)

    if not spans:
        return AnalysisReport(trace_id=trace.trace_id)

    # Compute wall-clock extent of the trace.
    earliest_start = min(s.start_time for s in spans)
    latest_end = max(s.end_time for s in spans)
    total_duration = latest_end - earliest_start

    llm_count = 0
    tool_count = 0
    error_count = 0
    prompt_tokens = 0
    completion_tokens = 0
    cost_usd = 0.0
    timeline: list[SpanSummary] = []
    errors: list[str] = []

    for span in sorted(spans, key=lambda s: s.start_time):
        timeline.append(
            SpanSummary(
                name=span.name,
                kind=span.kind,
                duration_s=span.duration_s,
                status=span.status,
            )
        )

        if span.kind == SpanKind.LLM:
            llm_count += 1
            prompt_tokens += int(span.attributes.get("prompt_tokens", 0))
            completion_tokens += int(span.attributes.get("completion_tokens", 0))
            cost_usd += float(span.attributes.get("cost_usd", 0.0))

        if span.kind == SpanKind.TOOL:
            tool_count += 1

        if span.status == SpanStatus.ERROR:
            error_count += 1
            error_detail = span.attributes.get("error", "(no detail)")
            errors.append(f"{span.name}: {error_detail}")

    return AnalysisReport(
        trace_id=trace.trace_id,
        span_count=len(spans),
        llm_call_count=llm_count,
        tool_call_count=tool_count,
        error_count=error_count,
        total_duration_s=total_duration,
        total_prompt_tokens=prompt_tokens,
        total_completion_tokens=completion_tokens,
        total_cost_usd=cost_usd,
        timeline=timeline,
        errors=errors,
    )
