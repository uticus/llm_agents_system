"""SpanMetricsBridge: translate a FinishedSpan into registry metric updates.

Calling :func:`bridge_span` on every finished span keeps the metrics registry
in sync with the live trace stream without requiring callers to manually
track counters or histograms.

This module never raises — all attribute access is guarded.  An unexpected
error emits a ``warnings.warn`` and returns normally so the collector's
export hook is never disrupted.

Metric name constants are defined at module level so that tests can assert
against them without hard-coding strings.
"""

from __future__ import annotations

import warnings

from llm_agents.infra.observability._metrics import MetricsRegistry, get_registry
from llm_agents.infra.tracing._models import FinishedSpan, SpanKind, SpanStatus

# ---------------------------------------------------------------------------
# Metric name constants (subsystem-relative; registry methods build full name)
# ---------------------------------------------------------------------------

SPANS_TOTAL = "spans_total"
"""Counter: total spans by kind and status.  Full name: ``llm_agents_spans_total``."""

SPAN_DURATION = "span_duration_seconds"
"""Histogram: wall-clock duration of every span by kind.
Full name: ``llm_agents_span_duration_seconds``."""

# LLM-specific constants are registered with subsystem="llm", so the registry
# produces full names like ``llm_agents_llm_{name}``.  The constant values must
# NOT include the "llm_" subsystem prefix — that is added by the registry.

LLM_REQUESTS = "requests_total"
"""Counter: LLM API calls by model and status.
Full name: ``llm_agents_llm_requests_total``."""

LLM_ERRORS = "errors_total"
"""Counter: LLM API calls that ended in ERROR status.
Full name: ``llm_agents_llm_errors_total``."""

LLM_LATENCY = "latency_seconds"
"""Histogram: LLM call latency from span attribute ``latency_s``.
Full name: ``llm_agents_llm_latency_seconds``."""

LLM_PROMPT_TOKENS = "prompt_tokens_total"
"""Counter: prompt token usage from span attribute ``prompt_tokens``.
Full name: ``llm_agents_llm_prompt_tokens_total``."""

LLM_COMPLETION_TOKENS = "completion_tokens_total"
"""Counter: completion token usage from span attribute ``completion_tokens``.
Full name: ``llm_agents_llm_completion_tokens_total``."""

LLM_COST = "cost_usd_total"
"""Counter: estimated cost in USD from span attribute ``cost_usd``.
Full name: ``llm_agents_llm_cost_usd_total``."""


# ---------------------------------------------------------------------------
# Bridge function
# ---------------------------------------------------------------------------


def bridge_span(
    span: FinishedSpan,
    registry: MetricsRegistry | None = None,
) -> None:
    """Update registry metrics from a finished *span*.

    Always updates:
        - ``llm_agents_spans_total{kind, status}``
        - ``llm_agents_span_duration_seconds{kind}``

    For :attr:`SpanKind.LLM` spans additionally:
        - ``llm_agents_llm_requests_total{model, status}``
        - ``llm_agents_llm_errors_total{model}`` (only when status is ERROR)
        - ``llm_agents_llm_latency_seconds{model}`` (if ``latency_s`` present)
        - ``llm_agents_llm_prompt_tokens_total{model}`` (if ``prompt_tokens`` present)
        - ``llm_agents_llm_completion_tokens_total{model}`` (if ``completion_tokens`` present)
        - ``llm_agents_llm_cost_usd_total{model}`` (if ``cost_usd`` present)

    Missing attributes are silently skipped.  Any unexpected exception is
    caught, emitted as a :class:`UserWarning`, and suppressed so that the
    caller's export hook is never disrupted.

    Args:
        span:     The finished span to bridge.
        registry: Registry to update.  Defaults to the module-level singleton.
    """
    r: MetricsRegistry = registry if registry is not None else get_registry()
    try:
        # --- Always ---
        r.counter(
            SPANS_TOTAL,
            help="Total spans finished by kind and status.",
            labels={"kind": span.kind.value, "status": span.status.value},
        ).inc()
        r.histogram(
            SPAN_DURATION,
            help="Wall-clock duration of finished spans in seconds.",
            labels={"kind": span.kind.value},
        ).observe(span.duration_s)

        # --- LLM spans only ---
        if span.kind == SpanKind.LLM:
            model: str = span.attributes.get("model", "unknown")

            r.counter(
                LLM_REQUESTS,
                help="Total LLM API requests by model and status.",
                subsystem="llm",
                labels={"model": model, "status": span.status.value},
            ).inc()

            if span.status == SpanStatus.ERROR:
                r.counter(
                    LLM_ERRORS,
                    help="Total LLM API requests that ended in error.",
                    subsystem="llm",
                    labels={"model": model},
                ).inc()

            if "latency_s" in span.attributes:
                r.histogram(
                    LLM_LATENCY,
                    help="LLM call latency in seconds.",
                    subsystem="llm",
                    labels={"model": model},
                ).observe(span.attributes["latency_s"])

            if "prompt_tokens" in span.attributes:
                r.counter(
                    LLM_PROMPT_TOKENS,
                    help="Total prompt tokens consumed.",
                    subsystem="llm",
                    labels={"model": model},
                ).inc(span.attributes["prompt_tokens"])

            if "completion_tokens" in span.attributes:
                r.counter(
                    LLM_COMPLETION_TOKENS,
                    help="Total completion tokens generated.",
                    subsystem="llm",
                    labels={"model": model},
                ).inc(span.attributes["completion_tokens"])

            if "cost_usd" in span.attributes:
                r.counter(
                    LLM_COST,
                    help="Total estimated cost in USD.",
                    subsystem="llm",
                    labels={"model": model},
                ).inc(span.attributes["cost_usd"])

    except Exception as exc:  # noqa: BLE001
        warnings.warn(
            f"bridge_span: unexpected error processing span '{span.name}': {exc}",
            UserWarning,
            stacklevel=2,
        )
