"""Versioned JSON serialization for :class:`Trace` objects.

The top-level ``schema_version`` field allows ``replay_analysis`` to detect
schema mismatches and evolve its reader without breaking on old recordings.
"""

from __future__ import annotations

import warnings
from typing import Any

from llm_agents.infra.tracing._models import FinishedSpan, SpanKind, SpanStatus, Trace

SCHEMA_VERSION: int = 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def serialize_trace(trace: Trace) -> dict[str, Any]:
    """Return a JSON-serializable ``dict`` representing *trace*.

    The returned dict can be passed directly to ``json.dumps`` provided all
    attribute values are JSON primitives (str, int, float, bool, None, list,
    dict).
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "trace_id": trace.trace_id,
        "spans": [_serialize_span(s) for s in trace.spans],
    }


def deserialize_trace(data: dict[str, Any]) -> Trace:
    """Reconstruct a :class:`Trace` from a previously serialized dict.

    Emits a :class:`UserWarning` if ``schema_version`` does not match
    :data:`SCHEMA_VERSION` (forward-compatibility signal, not a hard error).

    Raises:
        ValueError: if required top-level or span-level fields are missing.
    """
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        warnings.warn(
            f"Unknown trace schema_version {version!r}; expected {SCHEMA_VERSION}. "
            "Fields may be missing or incorrectly typed.",
            stacklevel=2,
        )
    try:
        trace_id: str = data["trace_id"]
        raw_spans: list[dict[str, Any]] = data["spans"]
    except KeyError as exc:
        raise ValueError(f"Missing required field in trace data: {exc}") from exc

    spans = tuple(_deserialize_span(s) for s in raw_spans)
    return Trace(trace_id=trace_id, spans=spans)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _serialize_span(span: FinishedSpan) -> dict[str, Any]:
    return {
        "trace_id": span.trace_id,
        "span_id": span.span_id,
        "parent_id": span.parent_id,
        "name": span.name,
        "kind": span.kind.value,
        "start_time": span.start_time,
        "start_wall": span.start_wall,
        "end_time": span.end_time,
        "duration_s": span.duration_s,
        "status": span.status.value,
        "attributes": dict(span.attributes),
    }


def _deserialize_span(data: dict[str, Any]) -> FinishedSpan:
    try:
        return FinishedSpan(
            trace_id=data["trace_id"],
            span_id=data["span_id"],
            parent_id=data["parent_id"],
            name=data["name"],
            kind=SpanKind(data["kind"]),
            start_time=float(data["start_time"]),
            start_wall=data["start_wall"],
            end_time=float(data["end_time"]),
            duration_s=float(data["duration_s"]),
            status=SpanStatus(data["status"]),
            attributes=dict(data["attributes"]),
        )
    except KeyError as exc:
        raise ValueError(f"Missing required field in span data: {exc}") from exc
