"""Observability subsystem: metrics, structured logging, and span-to-metrics bridge.

Public surface
--------------
Metric primitives and registry::

    from llm_agents.infra.observability import (
        Counter, Gauge, Histogram, DEFAULT_BUCKETS,
        MetricsRegistry, get_registry,
    )

Structured JSON logger::

    from llm_agents.infra.observability import get_logger
    log = get_logger(__name__)
    log.info("model called", model="gpt-4o")

Span metrics bridge::

    from llm_agents.infra.observability import bridge_span
    bridge_span(finished_span)

See :mod:`llm_agents.infra.observability._metrics`,
:mod:`llm_agents.infra.observability._logging`, and
:mod:`llm_agents.infra.observability._bridge` for implementation details.
"""

from llm_agents.infra.observability._bridge import bridge_span
from llm_agents.infra.observability._logging import StructuredLogger, get_logger
from llm_agents.infra.observability._metrics import (
    DEFAULT_BUCKETS,
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_registry,
)

__all__ = [
    "Counter",
    "DEFAULT_BUCKETS",
    "Gauge",
    "Histogram",
    "MetricsRegistry",
    "StructuredLogger",
    "bridge_span",
    "get_logger",
    "get_registry",
]
