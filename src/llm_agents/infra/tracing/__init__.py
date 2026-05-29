"""Tracing: capture structured spans across agent, tool, and LLM calls.

Public surface (import from here, never from private submodules)::

    from llm_agents.infra.tracing import tracer, traced, SpanKind, get_collector

Quick-start::

    from llm_agents.infra.tracing import tracer, SpanKind

    with tracer.span("my_op", SpanKind.TOOL, source="pg") as span:
        span.attributes["rows"] = 42

    @traced("llm_call", SpanKind.LLM, model="gpt-4o")
    async def call_model(prompt: str) -> str: ...
"""

from llm_agents.infra.tracing._collector import InMemoryCollector, get_collector
from llm_agents.infra.tracing._context import current_span
from llm_agents.infra.tracing._models import FinishedSpan, Span, SpanKind, SpanStatus, Trace
from llm_agents.infra.tracing._serialization import (
    SCHEMA_VERSION,
    deserialize_trace,
    serialize_trace,
)
from llm_agents.infra.tracing._tracer import Tracer, traced, tracer

__all__ = [
    # data model
    "SpanStatus",
    "SpanKind",
    "Span",
    "FinishedSpan",
    "Trace",
    # context
    "current_span",
    # tracer
    "Tracer",
    "tracer",
    "traced",
    # collector
    "InMemoryCollector",
    "get_collector",
    # serialization
    "serialize_trace",
    "deserialize_trace",
    "SCHEMA_VERSION",
]
