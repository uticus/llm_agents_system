"""Async-safe span context propagation via contextvars.

Uses ``contextvars.ContextVar`` so that each asyncio Task (coroutine) gets its
own current-span slot.  Thread-local storage is explicitly forbidden here per
ADR-002 — a single event-loop thread runs many coroutines simultaneously, so
a thread-local would corrupt the trace tree.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

from llm_agents.infra.tracing._models import Span

# The single authoritative variable for the active span.
# Named "current_span" so it appears clearly in stack / context dumps.
_current_span: ContextVar[Span | None] = ContextVar("current_span", default=None)


def current_span() -> Span | None:
    """Return the innermost active :class:`Span` in the current async context.

    Returns ``None`` when called outside a traced block.
    """
    return _current_span.get()


def _set_span(span: Span | None) -> Token:
    """Set the current span and return a restoration token.

    Private — only ``_tracer._SpanContext`` should call this.
    """
    return _current_span.set(span)


def _reset_span(token: Token) -> None:
    """Restore the previous span using the token returned by :func:`_set_span`.

    Private — only ``_tracer._SpanContext`` should call this.
    """
    _current_span.reset(token)
