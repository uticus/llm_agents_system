"""In-memory trace collector with a pluggable export hook.

The module-level singleton is accessed via :func:`get_collector`.  Tests must
call ``get_collector().reset()`` in their setUp / teardown to ensure isolation.
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from collections.abc import Callable

from llm_agents.infra.tracing._models import FinishedSpan, Trace


class InMemoryCollector:
    """Accumulates :class:`FinishedSpan` objects and assembles them into traces.

    An optional export hook is called synchronously after each span is added.
    Hook exceptions are caught and forwarded to :func:`warnings.warn` so they
    never interfere with the traced code path.
    """

    def __init__(self) -> None:
        self._spans: list[FinishedSpan] = []
        self._hook: Callable[[FinishedSpan], None] | None = None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(self, span: FinishedSpan) -> None:
        """Record *span* and invoke the export hook (if set)."""
        self._spans.append(span)
        if self._hook is not None:
            try:
                self._hook(span)
            except Exception as exc:  # noqa: BLE001
                warnings.warn(
                    f"Tracing export hook raised an exception: {exc}",
                    stacklevel=2,
                )

    def set_export_hook(self, hook: Callable[[FinishedSpan], None] | None) -> None:
        """Register (or clear) the export hook.

        The hook is called once per finished span, in the caller's context.
        Set to ``None`` to disable.
        """
        self._hook = hook

    def reset(self) -> None:
        """Clear all recorded spans and the export hook.

        Call this in test setUp / teardown to guarantee test isolation.
        """
        self._spans.clear()
        self._hook = None

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_trace(self, trace_id: str) -> Trace | None:
        """Return all spans for *trace_id* as a :class:`Trace`, or ``None``."""
        spans = sorted(
            (s for s in self._spans if s.trace_id == trace_id),
            key=lambda s: s.start_time,
        )
        if not spans:
            return None
        return Trace(trace_id=trace_id, spans=tuple(spans))

    def all_traces(self) -> list[Trace]:
        """Return all recorded traces, each with spans ordered by ``start_time``."""
        groups: dict[str, list[FinishedSpan]] = defaultdict(list)
        for span in self._spans:
            groups[span.trace_id].append(span)
        return [
            Trace(
                trace_id=tid,
                spans=tuple(sorted(spans, key=lambda s: s.start_time)),
            )
            for tid, spans in groups.items()
        ]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_collector = InMemoryCollector()


def get_collector() -> InMemoryCollector:
    """Return the shared :class:`InMemoryCollector` singleton."""
    return _collector
