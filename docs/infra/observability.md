# observability

Module path: `src/llm_agents/infra/observability/`

## Overview

The observability module provides three tightly integrated capabilities: a metrics subsystem (Counter, Gauge, Histogram, MetricsRegistry), a structured JSON logger (StructuredLogger, get_logger), and a span-to-metrics bridge (bridge_span). Together they ensure that every LLM call, every agent step, and every tool invocation produces both machine-readable log lines and numeric metrics that can be scraped by Prometheus — all from a single import, without an external metrics client library. The module is intentionally self-contained: it emits Prometheus text exposition format from pure Python stdlib, and it correlates log lines with the active tracing span by reading from `infra.tracing.current_span()` at log time, so operators can join logs and traces without a separate log shipper.

---

## Public API

Import everything from `llm_agents.infra.observability`.

### Exported symbols

| Symbol | Kind | Description |
|---|---|---|
| `Counter` | dataclass | Monotonically increasing numeric counter. |
| `Gauge` | dataclass | Numeric gauge that can increase or decrease. |
| `Histogram` | class | Sampling histogram with configurable buckets. |
| `DEFAULT_BUCKETS` | `tuple[float, ...]` | Default latency buckets matching Prometheus client defaults. |
| `MetricsRegistry` | class | Central store; creates and deduplicates metric instances; exports Prometheus text. |
| `get_registry` | function | Return the shared `MetricsRegistry` singleton. |
| `StructuredLogger` | class | Thin stdlib-logging wrapper that emits one JSON object per log line. |
| `get_logger` | function | Return (or create) a cached `StructuredLogger` for a given name. |
| `bridge_span` | function | Translate a `FinishedSpan` into registry metric updates. |

### `Counter`

```python
@dataclass
class Counter
```

| Method/Property | Signature | Description |
|---|---|---|
| `inc` | `(value: float = 1.0) -> None` | Increment by `value`. Never decrements. |
| `value` | `-> float` (property) | Current accumulated value. |

### `Gauge`

```python
@dataclass
class Gauge
```

| Method/Property | Signature | Description |
|---|---|---|
| `set` | `(value: float) -> None` | Set to an absolute value. |
| `inc` | `(value: float = 1.0) -> None` | Increment by `value`. |
| `dec` | `(value: float = 1.0) -> None` | Decrement by `value`. |
| `value` | `-> float` (property) | Current gauge value. |

### `Histogram`

```python
class Histogram
    def __init__(self, buckets: tuple[float, ...] = DEFAULT_BUCKETS) -> None
```

| Method/Property | Signature | Description |
|---|---|---|
| `observe` | `(value: float) -> None` | Record one observation. |
| `count` | `-> int` (property) | Total number of observations. |
| `sum` | `-> float` (property) | Sum of all observed values. |
| `buckets` | `() -> list[tuple[float, int]]` | Return `[(le, cumulative_count), ...]` including `+Inf`. |

### `MetricsRegistry`

```python
class MetricsRegistry
```

| Method | Signature | Description |
|---|---|---|
| `counter` | `(name, help="", labels=None, subsystem="") -> Counter` | Return or create a Counter. Appends `_total` suffix automatically. |
| `gauge` | `(name, help="", labels=None, subsystem="") -> Gauge` | Return or create a Gauge. |
| `histogram` | `(name, help="", labels=None, subsystem="", buckets=None) -> Histogram` | Return or create a Histogram. |
| `export` | `() -> str` | Generate Prometheus text exposition format for all metrics. |
| `reset` | `() -> None` | Clear all metrics. Use in test teardown. |

Metrics are deduplicated by `(full_name, frozenset_of_labels)`. Calling `counter("foo", labels={"a": "1"})` twice returns the same `Counter` instance.

Full metric names follow the pattern `llm_agents_{subsystem}_{name}` when `subsystem` is provided, or `llm_agents_{name}` otherwise.

### `StructuredLogger`

```python
class StructuredLogger
    def __init__(self, name: str) -> None
```

| Method | Signature | Description |
|---|---|---|
| `debug` | `(msg: str, **extra: Any) -> None` | Log at DEBUG level. |
| `info` | `(msg: str, **extra: Any) -> None` | Log at INFO level. |
| `warning` | `(msg: str, **extra: Any) -> None` | Log at WARNING level. |
| `error` | `(msg: str, **extra: Any) -> None` | Log at ERROR level. |
| `critical` | `(msg: str, **extra: Any) -> None` | Log at CRITICAL level. |

All keyword arguments passed to any log method become extra fields in the JSON output.

### `bridge_span`

```python
def bridge_span(
    span: FinishedSpan,
    registry: MetricsRegistry | None = None,
) -> None
```

Updates the registry with metrics derived from `span`. Never raises; unexpected errors are emitted as `UserWarning` and suppressed.

---

## Architecture

### Conceptual view

```
StructuredLogger                  MetricsRegistry
    |                                   |
    | get_logger(name)                  | get_registry()
    v                                   v
JSONFormatter                   Counter / Gauge / Histogram
    |                                   ^
    | reads current_span() from         |
    | llm_agents.infra.tracing          |
    v                          bridge_span(FinishedSpan)
  stdout JSON line                      ^
                                        |
                        InMemoryCollector.export_hook
                                        |
                                 Router / _SpanContext
                                 (tracing subsystem)
```

### Data flow

#### Logging path

1. Caller calls `log.info("model called", model="gpt-4o", tokens=256)`.
2. `StructuredLogger._log` calls `self._logger.log(level, msg, extra={"_extra": kwargs})`.
3. `JSONFormatter.format` reads `current_span()` from the tracing module (deferred import avoids circular dependency).
4. The formatter assembles a dict with fixed fields (`timestamp`, `level`, `logger`, `message`, `trace_id`, `span_id`) plus the caller's `**extra` kwargs.
5. `json.dumps(data)` produces the single-line JSON string written to stdout.

#### Metrics path

1. Any code calls `get_registry().counter("name", labels={"k": "v"}).inc()`.
2. The registry stores the `Counter` instance keyed by `(full_name, frozenset(labels.items()))`.
3. At scrape time, a route handler (not in this module) calls `get_registry().export()`.
4. The registry iterates all stored metric instances and renders Prometheus text exposition format: `# HELP`, `# TYPE`, and value lines for each instance.

#### Span bridge path

1. The `Router` registers `bridge_span` as the `InMemoryCollector` export hook.
2. When `_SpanContext._close()` calls `get_collector().add(finished_span)`, the hook fires.
3. `bridge_span` increments `llm_agents_spans_total{kind, status}` and observes `llm_agents_span_duration_seconds{kind}` for every span.
4. For `SpanKind.LLM` spans, it additionally increments LLM-specific counters and histograms keyed by `model`: `llm_agents_llm_requests_total`, `llm_agents_llm_errors_total` (error only), `llm_agents_llm_latency_seconds`, `llm_agents_llm_prompt_tokens_total`, `llm_agents_llm_completion_tokens_total`, `llm_agents_llm_cost_usd_total`.

### Key abstractions

**`JSONFormatter`:** A `logging.Formatter` subclass that converts a `LogRecord` to a JSON string. It reads `record._extra` (set by `StructuredLogger._log`) for caller-supplied fields. The deferred import of `current_span` breaks the circular dependency that would arise if the tracing module imported observability at module level.

**`MetricsRegistry` deduplication key:** The key `(full_name, frozenset(labels.items()))` ensures that two calls with the same name and labels return the same metric object, which is the Prometheus model for label dimensions. Frozenset is used because label dicts are unordered.

**`bridge_span` metric name constants:** `SPANS_TOTAL`, `SPAN_DURATION`, `LLM_REQUESTS`, `LLM_ERRORS`, `LLM_LATENCY`, `LLM_PROMPT_TOKENS`, `LLM_COMPLETION_TOKENS`, `LLM_COST` are module-level string constants so that tests can assert exact metric names without hard-coding strings.

**`DEFAULT_BUCKETS`:** Matches the default bucket boundaries from the official `prometheus_client` Python library, making the histogram output compatible with existing Grafana dashboards built against that library.

---

## Design decisions and tradeoffs

- **Decision:** No `prometheus_client` dependency; pure stdlib Prometheus exposition. **Why:** The `prometheus_client` library pulls in multiprocessing mode complexity and is incompatible with some deployment configurations. Pure stdlib removes the dependency and gives full control over the output format. **Tradeoff:** Missing built-in multiprocess mode, push gateway support, and process metrics (CPU, memory). These would need to be added manually if required.

- **Decision:** `StructuredLogger` wraps stdlib `logging` rather than replacing it. **Why:** Allows interoperation with existing logging configuration, handlers (e.g., file handlers), and third-party libraries that emit to the root logger. **Tradeoff:** Handler setup (one `StreamHandler` to stdout with `JSONFormatter`) is added heuristically when no handlers are present on the logger or root logger; in complex logging configurations this can result in double-logging.

- **Decision:** Trace and span IDs are injected into log lines by reading `current_span()` at format time. **Why:** No changes needed at call sites; any log line emitted inside a traced block is automatically correlated with the active trace. **Tradeoff:** The formatter imports from the tracing module at runtime (deferred import), creating an implicit coupling that is invisible to static analysis.

- **Decision:** `bridge_span` never raises. **Why:** It runs inside the collector's export hook, which itself catches exceptions. A double-exception scenario would be confusing; silently warning is safer for a side-channel metrics update. **Tradeoff:** Metric update failures are silent in production unless someone monitors the warnings stream.

- **Decision:** Metrics are deduplicated at the registry level rather than being global singletons. **Why:** Allows tests to call `get_registry().reset()` and get a clean state without importing every metric by name. **Tradeoff:** Callers that look up a metric by name get a new object after `reset()`, so they must re-fetch rather than caching the metric instance across a reset boundary.

---

## Scaling concerns

- **Registry memory:** All metric instances are stored in a dict keyed by `(full_name, frozenset)`. With many label combinations (high cardinality — e.g., one label per user ID), the store grows without bound. High-cardinality labels should not be used with this registry.

- **`export()` performance:** `export()` iterates all stored metric instances and renders text. With thousands of label combinations, this becomes a CPU-intensive operation on every scrape. Consider caching the export output with a short TTL.

- **Logging throughput:** `JSONFormatter.format` calls `json.dumps` on every log record. Under very high log volume (millions of records per minute), this can become a bottleneck. Moving to a faster JSON serializer (e.g., `orjson`) or async logging would be needed.

- **No labels validation:** The registry does not validate that all instances of a metric family use the same label names. Inconsistent label sets between calls produce Prometheus output that violates the format specification and will be rejected by Prometheus scrapers.

- **Single-process only:** The `MetricsRegistry` is in-process memory. Multi-process deployments (e.g., multiple uvicorn workers) will have separate, independent registries with no aggregation.

---

## Future improvements

- **High-cardinality protection:** Add a `max_label_combinations` guard per metric family that refuses to create new label-set instances above the limit, preventing unbounded registry growth.

- **Async-safe logging handler:** Add an `AsyncStreamHandler` that enqueues log records to an in-process queue and drains it in a background task, preventing slow I/O from blocking the event loop.

- **Multiprocess registry aggregation:** Implement a file-based or shared-memory metric store compatible with Prometheus multiprocess mode so that multiple workers present a unified view.

- **Scrape endpoint helper:** Add a lightweight ASGI/WSGI-compatible handler that serves `get_registry().export()` at `/metrics` with the correct `Content-Type: text/plain; version=0.0.4` header.

- **Log level control:** Expose a `set_level(level: int)` method on `StructuredLogger` so that log levels can be adjusted at runtime without reconfiguring the underlying stdlib logger directly.

---

## Usage examples

### Structured logging with trace correlation

```python
from llm_agents.infra.observability import get_logger
from llm_agents.infra.tracing import tracer, SpanKind

log = get_logger(__name__)

async def call_llm(prompt: str) -> str:
    async with tracer.span("llm_call", SpanKind.LLM, model="gpt-4o"):
        log.info("sending prompt", length=len(prompt), model="gpt-4o")
        result = await provider.complete(prompt)
        log.info("received response", tokens=result.usage.total_tokens)
        return result.content
# Each log line includes trace_id and span_id matching the active span.
```

### Metrics registration and export

```python
from llm_agents.infra.observability import get_registry

registry = get_registry()

# Create or retrieve metric instances
requests = registry.counter(
    "requests",
    help="Total tool invocations.",
    labels={"tool": "vector_search"},
    subsystem="tools",
)
latency = registry.histogram(
    "latency_seconds",
    help="Tool call latency.",
    labels={"tool": "vector_search"},
    subsystem="tools",
)

requests.inc()
latency.observe(0.042)

print(registry.export())
# llm_agents_tools_requests_total{tool="vector_search"} 1.0
# llm_agents_tools_latency_seconds_bucket{le="0.05",tool="vector_search"} 1
# ...
```

### Span-to-metrics bridge

```python
from llm_agents.infra.observability import bridge_span, get_registry
from llm_agents.infra.tracing import get_collector

# Register bridge_span as the collector export hook
get_collector().set_export_hook(bridge_span)

# After any traced LLM call, metrics are automatically updated:
# llm_agents_spans_total{kind="llm", status="ok"} ...
# llm_agents_llm_requests_total{model="gpt-4o", status="ok"} ...
# llm_agents_llm_latency_seconds_bucket{model="gpt-4o", le="..."} ...

print(get_registry().export())
```
