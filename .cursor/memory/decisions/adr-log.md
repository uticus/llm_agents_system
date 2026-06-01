# ADR Log
# File: .cursor/memory/decisions/adr-log.md
# Maintained by: Memory writer

> Authoritative log of all architectural decisions for this project.
> Each ADR is numbered sequentially. ADR numbers are never reused.
> Agents read this before making design decisions to check for existing constraints.
>
> [SETUP] This file is created by Memory writer when the first ADR is recorded.
> Until then it does not exist — agents note "No ADRs yet" and proceed from first principles.

---

## ADR-001: Minimal internal span model with OTel-adapter seam
Date: 2026-05-28
Status: accepted
Task: task-001

### Context
The tracing subsystem needs a span/trace data model. The open question was whether to
adopt the OpenTelemetry SDK now or build a minimal internal model. The project's
light-core principle forbids heavy third-party dependencies in the default install.

### Decision
Use a minimal internal data model (pure Python dataclasses) whose concepts and naming
align with OpenTelemetry (trace_id, span_id, parent_span_id, SpanKind, SpanStatus,
attributes) but carry no OpenTelemetry SDK dependency. A pluggable export hook on the
collector provides the seam where a future OTel exporter can be attached without
changing the internal model.

### Alternatives considered
- Full OTel SDK adoption: rejected — heavy dependency (opentelemetry-sdk + exporter
  packages), violates light-core principle, over-engineered for initial internal use.
- Completely custom model with no OTel alignment: rejected — would make a future OTel
  adapter unnecessarily painful and lose the benefit of a well-understood standard schema.

### Consequences
- Positive: zero external dependencies, fast import, easy to test, future OTel adapter
  is straightforward to add.
- Negative: must maintain alignment with OTel concepts manually; adapter must be written
  when OTel export is needed.

### Constraints imposed
- No `import opentelemetry` anywhere in `infra/tracing/`.
- Span/trace field names follow OTel naming (`trace_id`, `span_id`, `parent_span_id`,
  `SpanKind`, `SpanStatus`, `attributes`).
- Export hook signature: `Callable[[FinishedSpan], None]` — OTel exporter adapter plugs
  in here.

---

## ADR-002: contextvars.ContextVar for async-safe span context propagation
Date: 2026-05-28
Status: accepted
Task: task-001

### Context
The tracing subsystem needs to track "current span" across nested async calls. Python
agents run concurrently via asyncio (FastAPI, async tool calls). A naive thread-local
would corrupt context across coroutines sharing one OS thread.

### Decision
Use `contextvars.ContextVar[Span | None]` (stdlib, Python 3.7+) named `"current_span"`
as the sole mechanism for span context propagation. This is the project-wide pattern for
all request-scoped context that must be coroutine-safe.

### Alternatives considered
- `threading.local`: rejected — single event-loop thread runs many coroutines; all
  coroutines would share one "current span", corrupting the trace tree.
- Explicit span parameter threading (pass span to every function): rejected — impractical
  and breaks the decorator use-case entirely.

### Consequences
- Positive: correct for asyncio; works in thread-pool executors too (context is copied);
  zero cost; no external dep.
- Negative: requires callers who spawn asyncio Tasks to be aware that context is copied
  at Task creation (child task inherits parent's current_span at spawn time, not at await
  time — this is correct and desirable for tracing).

### Constraints imposed
- `threading.local` is explicitly forbidden for span context in this project.
- All context-scoped state that must be coroutine-safe MUST use `contextvars.ContextVar`.
- Any `asyncio.Task` spawned inside a traced block automatically inherits the parent span
  context — implementers must not manually copy or pass the span.

---

## ADR-003: Prometheus text format generated in pure stdlib
Date: 2026-05-28
Status: accepted
Task: task-002

### Context
The observability module needs a Prometheus-compatible metrics export path.
The project's light-core principle forbids external dependencies in the default install.

### Decision
Generate the Prometheus text exposition format using stdlib string building only.
No `prometheus_client` package is imported. The `MetricsRegistry.export()` method
produces a valid Prometheus text format string that any scraper can consume.

### Alternatives considered
- Use `prometheus_client`: rejected — external dependency, violates light-core principle;
  adds ~100 KB and background threads; overkill for the internal use case.
- Use OTLP push: rejected — heavier, requires network, adds agent overhead; pull scrape
  aligns with the existing configs/observability/prometheus.yml config.

### Consequences
- Positive: zero external dependencies; fast; fully controllable format output.
- Negative: must maintain Prometheus format compliance manually; future format evolution
  (e.g., OpenMetrics) requires custom work.

### Constraints imposed
- No `import prometheus_client` anywhere in `infra/observability/`.
- Metric names follow `llm_agents_{subsystem}_{name}_{unit}` convention.
- Counter names must end in `_total` per Prometheus naming convention.
- Histogram `+Inf` bucket must always be present.

---

## ADR-004: Structured logger wraps stdlib logging with JSON formatter
Date: 2026-05-28
Status: accepted
Task: task-002

### Context
The observability module needs structured JSON logging with trace/span correlation.
The project's light-core principle forbids heavy logging frameworks.

### Decision
Implement `StructuredLogger` as a thin wrapper around a stdlib `logging.Logger`
with a custom `JSONFormatter`. Each log call adds `trace_id` and `span_id` from
`infra/tracing.current_span()` to the JSON output automatically.

### Alternatives considered
- `structlog`: rejected — external dependency, violates light-core principle; the
  required feature set (JSON output + context injection) is achievable with stdlib.
- `loguru`: rejected — same reason; also changes global logging behavior.

### Consequences
- Positive: zero external dependencies; integrates with stdlib logging ecosystem;
  compatible with existing logging configuration.
- Negative: JSON formatting is custom; must maintain compatibility with stdlib
  logging API manually; no built-in log pipeline features.

### Constraints imposed
- No third-party logging library imports in `infra/observability/`.
- All log output is valid JSON (parseable by `json.loads`).
- `trace_id` and `span_id` fields are always present (null when no active span).

---

## ADR-005: Shared DeduplicationStore protocol in infra/cost_latency_optimization
Date: 2026-06-01
Status: accepted
Task: task-044

### Context
Both `data/ingestion.IngestionPipeline` and `rag/indexing.Indexer` maintain content-hash
deduplication via an in-process `set[str]` (`_seen_hashes`). This state is lost on process
restart, so unchanged documents are re-embedded and re-upserted on every cold start.
The project needed a durable backend option. Because both modules need the same abstraction,
a shared location was required to avoid duplication.

### Decision
Define a `DeduplicationStore` Protocol (plus `InMemoryDeduplicationStore` and
`SQLiteDeduplicationStore` concrete implementations) in
`infra/cost_latency_optimization/_dedup.py` and re-export from that package's `__init__`.
Both `data/ingestion` and `rag/indexing` import from `infra/cost_latency_optimization`
and re-export the three names from their own `__init__` for caller convenience.
Each consumer receives an optional keyword-only `dedup_store` parameter; `None` (default)
creates an `InMemoryDeduplicationStore` internally, preserving full backward compatibility.

### Alternatives considered
- Duplicate definition in each subpackage (`data/ingestion/_dedup.py` and
  `rag/indexing/_dedup.py`): rejected — two identical Protocol definitions violate DRY
  and create maintenance risk (divergence over time).
- New top-level `shared/` package: rejected — introduces a new layer not present in the
  existing architecture; both consumers already depend on `infra/`, making
  `infra/cost_latency_optimization` the natural home.
- Place in `data/` and import into `rag/`: rejected — creates a downward cross-subsystem
  dependency from `rag/` into `data/`, violating the intended layer boundaries where
  `data/` feeds `rag/`, not the other way around.

### Consequences
- Positive: single Protocol definition shared by both consumers; `SQLiteDeduplicationStore`
  enables durable incremental ingestion and indexing across process restarts; pluggable
  backend allows future Redis or DynamoDB implementations without touching consumers.
- Negative: callers who need durable deduplication must explicitly pass
  `SQLiteDeduplicationStore`; the default remains in-memory (by design, for backward compat).

### Constraints imposed
- `DeduplicationStore`, `InMemoryDeduplicationStore`, `SQLiteDeduplicationStore` live
  exclusively in `infra/cost_latency_optimization/_dedup.py`.
- No duplicate Protocol definition in `data/` or `rag/`; both import from `infra/`.
- `dedup_store` parameter MUST be keyword-only (`*` separator) in both consumers.
- `SQLiteDeduplicationStore` uses deferred `import sqlite3` inside `__init__` (project
  pattern for optional-path stdlib modules with potential absence in lightweight envs).
- Hash algorithm for all consumers remains MD5 via
  `hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()`.

---

<!-- ADRs will be appended here by Memory writer. Format:

## ADR-001: <title>
Date: <date>
Status: accepted | superseded by ADR-NNN
Task: task-NNN

### Context
<why this decision was needed>

### Decision
<what was decided>

### Alternatives considered
- <alternative 1>: <why rejected>
- <alternative 2>: <why rejected>

### Consequences
- Positive: <what becomes easier>
- Negative: <what becomes harder or constrained>

### Constraints imposed
<what Implementer must follow as a result>

-->
