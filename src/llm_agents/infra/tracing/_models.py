"""Data model for the tracing subsystem.

Defines the span and trace types used throughout the tracing pipeline.
All types are pure data; no business logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SpanStatus(StrEnum):
    """Terminal status of a finished span."""

    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


class SpanKind(StrEnum):
    """Semantic category of a span, aligned with OpenTelemetry naming."""

    INTERNAL = "internal"
    LLM = "llm"
    TOOL = "tool"
    AGENT = "agent"


@dataclass
class Span:
    """Live, mutable span open during a traced block.

    Created by ``_SpanContext.__enter__`` / ``__aenter__``.
    Never stored in the collector — use ``FinishedSpan`` for that.
    """

    trace_id: str
    span_id: str
    parent_id: str | None
    name: str
    kind: SpanKind
    start_time: float  # time.perf_counter() at open
    start_wall: str  # datetime.now(UTC).isoformat() at open
    status: SpanStatus = SpanStatus.UNSET
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinishedSpan:
    """Immutable snapshot of a span produced when the traced block exits.

    Written to the collector via ``InMemoryCollector.add()``.
    """

    trace_id: str
    span_id: str
    parent_id: str | None
    name: str
    kind: SpanKind
    start_time: float
    start_wall: str
    end_time: float
    duration_s: float  # end_time - start_time
    status: SpanStatus
    attributes: dict[str, Any]


@dataclass(frozen=True)
class Trace:
    """All finished spans that share a ``trace_id``, ordered by ``start_time``."""

    trace_id: str
    spans: tuple[FinishedSpan, ...]
