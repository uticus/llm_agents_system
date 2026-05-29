"""Metric primitives and registry for the observability subsystem.

Provides Counter, Gauge, and Histogram along with a MetricsRegistry that
accumulates all registered metrics and can export them as a Prometheus text
exposition format string (pure stdlib — no prometheus_client dependency, per ADR-003).

Metric naming convention (ADR-003):
    llm_agents_{subsystem}_{metric_name}_{unit_suffix}

Counter names automatically gain the ``_total`` suffix required by Prometheus.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# Default latency buckets — matches Prometheus client defaults.
DEFAULT_BUCKETS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

_INF = math.inf

# Prometheus metric type names used in # TYPE lines.
_TYPE_COUNTER = "counter"
_TYPE_GAUGE = "gauge"
_TYPE_HISTOGRAM = "histogram"


# ---------------------------------------------------------------------------
# Metric primitives
# ---------------------------------------------------------------------------


@dataclass
class Counter:
    """Monotonically increasing counter.

    Never decrements.  Use :meth:`inc` to add a non-negative value.
    """

    _value: float = field(default=0.0, init=False)

    def inc(self, value: float = 1.0) -> None:
        """Increment the counter by *value* (default 1.0)."""
        self._value += value

    @property
    def value(self) -> float:
        """Current accumulated value."""
        return self._value


@dataclass
class Gauge:
    """Arbitrary-value metric that can go up and down."""

    _value: float = field(default=0.0, init=False)

    def set(self, value: float) -> None:
        """Set the gauge to an absolute *value*."""
        self._value = value

    def inc(self, value: float = 1.0) -> None:
        """Increment the gauge by *value*."""
        self._value += value

    def dec(self, value: float = 1.0) -> None:
        """Decrement the gauge by *value*."""
        self._value -= value

    @property
    def value(self) -> float:
        """Current gauge value."""
        return self._value


class Histogram:
    """Sampling histogram that tracks count, sum, and per-bucket counts.

    Buckets are cumulative (each bucket ``le`` counts observations ``<= le``).
    A ``+Inf`` bucket is always present and equals the total observation count.
    """

    def __init__(self, buckets: tuple[float, ...] = DEFAULT_BUCKETS) -> None:
        sorted_b: list[float] = sorted(set(buckets))
        if not sorted_b or sorted_b[-1] < _INF:
            sorted_b.append(_INF)
        self._boundaries: list[float] = sorted_b
        self._counts: list[int] = [0] * len(sorted_b)
        self._sum: float = 0.0
        self._count: int = 0

    def observe(self, value: float) -> None:
        """Record a single observation of *value*."""
        self._count += 1
        self._sum += value
        for i, le in enumerate(self._boundaries):
            if value <= le:
                self._counts[i] += 1

    @property
    def count(self) -> int:
        """Total number of observations."""
        return self._count

    @property
    def sum(self) -> float:
        """Sum of all observed values."""
        return self._sum

    def buckets(self) -> list[tuple[float, int]]:
        """Return ``[(le, cumulative_count), ...]`` including the ``+Inf`` bucket.

        ``observe()`` already increments every bucket whose ``le`` value is >=
        the observed value, so ``_counts[i]`` is already the cumulative count
        for bucket *i*.  No further accumulation is needed here.
        """
        return list(zip(self._boundaries, self._counts, strict=True))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def _full_name(name: str, subsystem: str) -> str:
    """Build the full metric name: ``llm_agents_{subsystem}_{name}``."""
    if subsystem:
        return f"llm_agents_{subsystem}_{name}"
    return f"llm_agents_{name}"


def _format_labels(labels: dict[str, str] | None) -> str:
    """Format label dict as Prometheus label string ``{k="v",...}``."""
    if not labels:
        return ""
    parts: list[str] = []
    for k, v in sorted(labels.items()):
        escaped = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        parts.append(f'{k}="{escaped}"')
    return "{" + ",".join(parts) + "}"


class MetricsRegistry:
    """Central store for all metrics.

    Metrics are deduplicated by ``(full_name, label_set)`` — calling
    ``counter("foo", labels={"a": "1"})`` twice returns the same instance.

    Call :meth:`reset` in test setUp / teardown for isolation.
    """

    def __init__(self) -> None:
        # (full_name, frozenset of label items) -> metric instance
        self._store: dict[tuple[str, frozenset], Any] = {}
        # full_name -> help text (first registration wins)
        self._help: dict[str, str] = {}
        # full_name -> metric type
        self._type_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    def counter(
        self,
        name: str,
        help: str = "",
        labels: dict[str, str] | None = None,
        subsystem: str = "",
    ) -> Counter:
        """Return (or create) a :class:`Counter`.

        The ``_total`` suffix is appended automatically if not already present,
        per the Prometheus naming convention.
        """
        n = name if name.endswith("_total") else name + "_total"
        full = _full_name(n, subsystem)
        key = (full, frozenset((labels or {}).items()))
        if key not in self._store:
            self._store[key] = Counter()
            self._help.setdefault(full, help)
            self._type_map.setdefault(full, _TYPE_COUNTER)
        return self._store[key]  # type: ignore[return-value]

    def gauge(
        self,
        name: str,
        help: str = "",
        labels: dict[str, str] | None = None,
        subsystem: str = "",
    ) -> Gauge:
        """Return (or create) a :class:`Gauge`."""
        full = _full_name(name, subsystem)
        key = (full, frozenset((labels or {}).items()))
        if key not in self._store:
            self._store[key] = Gauge()
            self._help.setdefault(full, help)
            self._type_map.setdefault(full, _TYPE_GAUGE)
        return self._store[key]  # type: ignore[return-value]

    def histogram(
        self,
        name: str,
        help: str = "",
        labels: dict[str, str] | None = None,
        subsystem: str = "",
        buckets: tuple[float, ...] | None = None,
    ) -> Histogram:
        """Return (or create) a :class:`Histogram`."""
        full = _full_name(name, subsystem)
        key = (full, frozenset((labels or {}).items()))
        if key not in self._store:
            self._store[key] = Histogram(buckets if buckets is not None else DEFAULT_BUCKETS)
            self._help.setdefault(full, help)
            self._type_map.setdefault(full, _TYPE_HISTOGRAM)
        return self._store[key]  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(self) -> str:
        """Generate a Prometheus text exposition format string for all metrics."""
        # Group by full_name so TYPE/HELP headers appear once per metric family.
        groups: dict[str, list[tuple[frozenset, Any]]] = {}
        for (full_name, lset), metric in self._store.items():
            groups.setdefault(full_name, []).append((lset, metric))

        lines: list[str] = []
        for full_name, instances in groups.items():
            mtype = self._type_map[full_name]
            help_text = self._help.get(full_name, "")
            if help_text:
                lines.append(f"# HELP {full_name} {help_text}")
            lines.append(f"# TYPE {full_name} {mtype}")

            for lset, metric in instances:
                labels = dict(lset)
                lstr = _format_labels(labels)

                if mtype == _TYPE_COUNTER:
                    lines.append(f"{full_name}{lstr} {metric.value}")
                elif mtype == _TYPE_GAUGE:
                    lines.append(f"{full_name}{lstr} {metric.value}")
                elif mtype == _TYPE_HISTOGRAM:
                    for le, cum in metric.buckets():
                        le_str = "+Inf" if le == _INF else str(le)
                        bstr = _format_labels({**labels, "le": le_str})
                        lines.append(f"{full_name}_bucket{bstr} {cum}")
                    lines.append(f"{full_name}_sum{lstr} {metric.sum}")
                    lines.append(f"{full_name}_count{lstr} {metric.count}")

        return "\n".join(lines) + ("\n" if lines else "")

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all metrics.  Use in test setUp / teardown."""
        self._store.clear()
        self._help.clear()
        self._type_map.clear()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    """Return the shared :class:`MetricsRegistry` singleton."""
    return _registry
