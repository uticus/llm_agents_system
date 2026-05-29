"""Tracer: entry point for creating and instrumenting spans.

Provides a sync/async context manager (``Tracer.span``) and a decorator
factory (``Tracer.traced``) that both delegate span lifecycle to
``_SpanContext``.

Module-level convenience singletons ``tracer`` and ``traced`` are provided so
callers can write ``from llm_agents.infra.tracing import traced`` without
instantiating a ``Tracer`` themselves.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from time import perf_counter
from typing import Any
from uuid import uuid4

from llm_agents.infra.tracing._collector import get_collector
from llm_agents.infra.tracing._context import _reset_span, _set_span, current_span
from llm_agents.infra.tracing._models import FinishedSpan, Span, SpanKind, SpanStatus


class _SpanContext:
    """Dual-protocol (sync and async) context manager for a single span.

    Supports both ``with tracer.span(...)`` and ``async with tracer.span(...)``.
    The open/close logic lives in ``_open`` and ``_close`` to avoid duplication
    between the sync and async protocol methods.
    """

    __slots__ = ("_name", "_kind", "_attrs", "_span", "_token")

    def __init__(self, name: str, kind: SpanKind, attrs: dict[str, Any]) -> None:
        self._name = name
        self._kind = kind
        self._attrs = attrs
        self._span: Span | None = None
        self._token = None

    # ------------------------------------------------------------------
    # Core lifecycle — shared by sync and async paths
    # ------------------------------------------------------------------

    def _open(self) -> Span:
        parent = current_span()
        trace_id = parent.trace_id if parent is not None else uuid4().hex
        parent_id = parent.span_id if parent is not None else None
        span = Span(
            trace_id=trace_id,
            span_id=uuid4().hex,
            parent_id=parent_id,
            name=self._name,
            kind=self._kind,
            start_time=perf_counter(),
            start_wall=datetime.now(UTC).isoformat(),
            attributes=dict(self._attrs),
        )
        self._token = _set_span(span)
        self._span = span
        return span

    def _close(self, exc_type: type | None, exc_val: BaseException | None) -> bool:
        assert self._span is not None, "_close called before _open"  # noqa: S101
        span = self._span
        end_time = perf_counter()

        if exc_type is not None:
            span.status = SpanStatus.ERROR
            span.attributes["error"] = str(exc_val)
        elif span.status is SpanStatus.UNSET:
            span.status = SpanStatus.OK

        finished = FinishedSpan(
            trace_id=span.trace_id,
            span_id=span.span_id,
            parent_id=span.parent_id,
            name=span.name,
            kind=span.kind,
            start_time=span.start_time,
            start_wall=span.start_wall,
            end_time=end_time,
            duration_s=end_time - span.start_time,
            status=span.status,
            attributes=dict(span.attributes),
        )
        get_collector().add(finished)
        _reset_span(self._token)
        return False  # never suppress exceptions

    # ------------------------------------------------------------------
    # Sync protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> Span:
        return self._open()

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        tb: object,
    ) -> bool:
        return self._close(exc_type, exc_val)

    # ------------------------------------------------------------------
    # Async protocol
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Span:
        return self._open()

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        tb: object,
    ) -> bool:
        return self._close(exc_type, exc_val)


class Tracer:
    """Creates and manages spans via context managers and decorators."""

    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        **attrs: Any,
    ) -> _SpanContext:
        """Return a context manager (sync and async) that opens a new span.

        The span is automatically linked to the current span (if any) as its
        parent, using the ``contextvars``-based context.

        Args:
            name: Human-readable span name.
            kind: Semantic category — defaults to ``SpanKind.INTERNAL``.
            **attrs: Arbitrary key/value attributes attached to the span.

        Example::

            with tracer.span("fetch_context", SpanKind.TOOL, source="pg"):
                ...

            async with tracer.span("llm_call", SpanKind.LLM, model="gpt-4o"):
                ...
        """
        return _SpanContext(name=name, kind=kind, attrs=attrs)

    def traced(
        self,
        name: str | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        **attrs: Any,
    ) -> Callable:
        """Decorator factory that wraps a function in a span.

        Works on both sync and async functions.  The span name defaults to
        ``fn.__qualname__`` when *name* is not provided.

        Example::

            @tracer.traced("my_tool", SpanKind.TOOL, source="pg")
            def fetch(query: str) -> list[str]: ...

            @traced(kind=SpanKind.LLM)
            async def call_llm(prompt: str) -> str: ...
        """

        def decorator(fn: Callable) -> Callable:
            span_name = name if name is not None else fn.__qualname__

            if asyncio.iscoroutinefunction(fn):

                @wraps(fn)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    async with self.span(span_name, kind, **attrs):
                        return await fn(*args, **kwargs)

                return async_wrapper

            @wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.span(span_name, kind, **attrs):
                    return fn(*args, **kwargs)

            return sync_wrapper

        return decorator


# ---------------------------------------------------------------------------
# Module-level convenience singletons
# ---------------------------------------------------------------------------

tracer: Tracer = Tracer()
# Module-level alias; same object as tracer.traced — re-exported from __init__.py.
traced = tracer.traced
