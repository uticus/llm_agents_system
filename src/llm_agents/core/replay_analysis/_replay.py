"""Replay engine and divergence detection.

:class:`ReplayEngine` replays a recorded :class:`Trace` deterministically
without making any live provider calls.  It produces an ordered list of
:class:`SpanSummary` objects, one per span in the trace.

:func:`detect_divergence` compares two :class:`Trace` objects (e.g. a
recorded trace and a fresh run) and returns human-readable descriptions of
any structural or status differences.
"""

from __future__ import annotations

from llm_agents.core.replay_analysis._report import SpanSummary
from llm_agents.infra.tracing._models import SpanStatus, Trace


class ReplayEngine:
    """Deterministic trace replayer.

    No live provider calls are made.  The engine reads the recorded span
    sequence and re-materialises the execution timeline as
    :class:`SpanSummary` objects.

    Args:
        trace: The recorded :class:`Trace` to replay.
    """

    def __init__(self, trace: Trace) -> None:
        self._trace = trace

    def replay(self) -> list[SpanSummary]:
        """Return a :class:`SpanSummary` for each span, ordered by start time.

        Replay is purely data-driven: the span attributes are copied into
        summary objects without executing any tool or LLM logic.

        Returns:
            Ordered list of :class:`SpanSummary` objects.
        """
        summaries: list[SpanSummary] = []
        for span in sorted(self._trace.spans, key=lambda s: s.start_time):
            summaries.append(
                SpanSummary(
                    name=span.name,
                    kind=span.kind,
                    duration_s=span.duration_s,
                    status=span.status,
                )
            )
        return summaries

    @property
    def trace(self) -> Trace:
        """The :class:`Trace` being replayed."""
        return self._trace


def detect_divergence(recorded: Trace, fresh: Trace) -> list[str]:
    """Compare *recorded* and *fresh* traces and return divergence descriptions.

    Checks performed:
    - Span count mismatch.
    - Span name sequence mismatch (in order).
    - Per-span status mismatch (for spans present in both by position).

    Args:
        recorded: The baseline trace (e.g. loaded from a fixture file).
        fresh:    The newly produced trace to compare against.

    Returns:
        A list of human-readable divergence strings.  An empty list means
        no divergence was detected.
    """
    issues: list[str] = []

    rec_spans = sorted(recorded.spans, key=lambda s: s.start_time)
    fresh_spans = sorted(fresh.spans, key=lambda s: s.start_time)

    if len(rec_spans) != len(fresh_spans):
        issues.append(
            f"Span count differs: recorded={len(rec_spans)}, fresh={len(fresh_spans)}"
        )

    rec_names = [s.name for s in rec_spans]
    fresh_names = [s.name for s in fresh_spans]
    if rec_names != fresh_names:
        issues.append(
            f"Span name sequence differs: recorded={rec_names!r}, fresh={fresh_names!r}"
        )

    # Per-span status comparison (only for positions present in both).
    for i, (rec, frsh) in enumerate(zip(rec_spans, fresh_spans, strict=False)):
        if rec.status != frsh.status:
            issues.append(
                f"Span[{i}] '{rec.name}' status: "
                f"recorded={rec.status.value!r}, fresh={frsh.status.value!r}"
            )

    # Report spans with ERROR status in the recorded trace that were OK in fresh.
    for i, (rec, frsh) in enumerate(zip(rec_spans, fresh_spans, strict=False)):
        if rec.status == SpanStatus.ERROR and frsh.status != SpanStatus.ERROR:
            issues.append(
                f"Span[{i}] '{rec.name}' was ERROR in recorded trace but not in fresh run"
            )

    return issues
