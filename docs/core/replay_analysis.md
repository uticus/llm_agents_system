# replay_analysis

## Overview

The `replay_analysis` module provides post-run observability for agent executions. It loads recorded trace files (JSON format produced by the tracing infrastructure), replays them deterministically to reconstruct the execution timeline, analyzes span-level metrics (timing, token costs, error counts), and detects structural divergences between two traces (e.g. a baseline recording vs. a fresh run). The module exists because LLM agent behavior is non-deterministic and difficult to audit without structured execution records. By separating the act of recording (handled by the `infra.tracing` layer) from the act of analysis (handled here), the module can be used in CI regression testing, cost monitoring dashboards, and debugging workflows without requiring a live agent runtime.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `load_trace` | function | Load a `Trace` from a JSON file on disk. |
| `analyze` | function | Produce a structured `AnalysisReport` from a `Trace`. |
| `SpanSummary` | frozen dataclass | Lightweight per-span record used in timelines and replay output. |
| `AnalysisReport` | dataclass | Structured analysis of a recorded `Trace`. |
| `ReplayEngine` | class | Deterministic trace replayer. |
| `detect_divergence` | function | Compare two traces and return human-readable divergence descriptions. |

### `load_trace`

```python
def load_trace(path: str | Path) -> Trace
```

Raises `FileNotFoundError`, `json.JSONDecodeError`, or `ValueError` on error. Delegates deserialization to `llm_agents.infra.tracing._serialization.deserialize_trace`.

### `analyze`

```python
def analyze(trace: Trace) -> AnalysisReport
```

Returns an empty `AnalysisReport` (all zero fields) for a trace with no spans.

### `SpanSummary`

```python
@dataclass(frozen=True)
class SpanSummary:
    name: str
    kind: SpanKind
    duration_s: float
    status: SpanStatus
```

### `AnalysisReport`

```python
@dataclass
class AnalysisReport:
    trace_id: str
    span_count: int = 0
    llm_call_count: int = 0
    tool_call_count: int = 0
    error_count: int = 0
    total_duration_s: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    timeline: list[SpanSummary] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
```

### `ReplayEngine`

```python
ReplayEngine(trace: Trace)
```

| Method / Property | Signature | Description |
|---|---|---|
| `replay` | `() -> list[SpanSummary]` | Return `SpanSummary` for each span, ordered by `start_time`. |
| `trace` | property `-> Trace` | The `Trace` being replayed. |

### `detect_divergence`

```python
def detect_divergence(recorded: Trace, fresh: Trace) -> list[str]
```

Returns an empty list when no divergence is detected. Checks performed: span count mismatch, span name sequence mismatch, per-span status mismatch, and recorded-ERROR-but-fresh-OK spans.

---

## Architecture

### Conceptual view

```
  JSON file (trace fixture)
         |
     load_trace()
         |
       Trace
      (trace_id, spans: tuple[FinishedSpan, ...])
         |
   +-----+-----+
   |           |
analyze()   ReplayEngine
   |           |
AnalysisReport  list[SpanSummary]
   |
   +-- span_count, llm_call_count, tool_call_count
   +-- error_count, total_duration_s
   +-- total_prompt_tokens, total_completion_tokens, total_cost_usd
   +-- timeline: list[SpanSummary]
   +-- errors: list[str]

  Trace A (recorded)
  Trace B (fresh)
         |
  detect_divergence()
         |
  list[str]  (human-readable divergence descriptions)
```

All processing is read-only with respect to the `Trace`. No span data is mutated at any point.

### Data flow

**Load path:**

1. `load_trace(path)` reads the file at `path` as UTF-8 text.
2. `json.loads` parses the content into a Python dict.
3. `deserialize_trace` (from `infra.tracing._serialization`) validates required fields and constructs a `Trace` with a `tuple[FinishedSpan, ...]`.

**Analysis path:**

1. `analyze(trace)` extracts all `FinishedSpan` objects from `trace.spans`.
2. Spans are sorted by `start_time` ascending to establish the timeline order.
3. The earliest `start_time` and latest `end_time` across all spans are used to compute `total_duration_s` (wall-clock extent of the trace).
4. For each span:
   - A `SpanSummary` is appended to `timeline`.
   - If `span.kind == SpanKind.LLM`: `llm_call_count` is incremented; `prompt_tokens`, `completion_tokens`, and `cost_usd` attributes are read from `span.attributes` (defaulting to 0 if absent).
   - If `span.kind == SpanKind.TOOL`: `tool_call_count` is incremented.
   - If `span.status == SpanStatus.ERROR`: `error_count` is incremented; a string `"<name>: <error detail>"` is appended to `errors`.
5. An `AnalysisReport` is returned with all aggregated values.

**Replay path:**

1. `ReplayEngine.replay()` sorts spans by `start_time`.
2. For each span, a `SpanSummary` is constructed from `span.name`, `span.kind`, `span.duration_s`, and `span.status`.
3. No tool or LLM logic is executed — the replay is purely data-driven.

**Divergence detection path:**

1. Both `recorded` and `fresh` span sequences are sorted by `start_time`.
2. If span counts differ, one issue string is appended.
3. If span name sequences differ, one issue string with the full name lists is appended.
4. For positions present in both sequences, if `rec.status != frsh.status`, one issue string is appended per mismatched position.
5. For positions where `rec.status == ERROR` and `frsh.status != ERROR`, an additional issue string is appended (recorded error not reproduced in fresh run).

### Key abstractions

**`Trace` and `FinishedSpan`** (from `infra.tracing._models`) — the shared data contract between the recording infrastructure and the analysis layer. A `Trace` is immutable (`frozen=True` on `FinishedSpan`), which allows safe concurrent reading from multiple analysis functions.

**`SpanSummary`** — a lightweight projection of a `FinishedSpan` that excludes the trace/span/parent IDs, wall-clock start time string, and raw attributes dict. It contains only the information needed for display, comparison, and reporting, making it safe to serialize without leaking internal correlation IDs.

**`AnalysisReport`** — an aggregated view of a trace optimized for reporting rather than detailed forensics. It does not preserve individual span attributes; callers that need attribute-level details should iterate `trace.spans` directly.

**`ReplayEngine`** — separates the concept of "what happened" (the trace) from "how it is presented" (the replay). By not re-executing any logic, the engine guarantees determinism: the same trace always produces the same replay regardless of external state.

---

## Design decisions and tradeoffs

- **Decision**: `load_trace` delegates JSON parsing to `infra.tracing._serialization.deserialize_trace` rather than implementing its own parsing. **Why**: The serialization format is owned by the tracing infrastructure. Centralizing parsing in one place ensures that format changes only need to be updated in one location. **Tradeoff**: The analysis layer takes a hard dependency on the internal serialization module of the tracing infrastructure.

- **Decision**: `analyze` computes `total_duration_s` as `max(end_time) - min(start_time)` across all spans, not as a sum of span durations. **Why**: Spans can overlap (e.g. parent and child spans), so summing durations would double-count parallel work. The wall-clock extent gives the true elapsed time of the trace. **Tradeoff**: For traces with a single top-level span containing nested spans, this accurately reflects wall time, but for traces with gaps between unrelated spans, the reported duration may be larger than any individual operation.

- **Decision**: `detect_divergence` checks span name sequences positionally, not by alignment. **Why**: Positional comparison is O(n) and deterministic. Alignment-based comparison (e.g. diff/LCS) is O(n^2) and produces ambiguous results when spans are reordered. **Tradeoff**: If a fresh trace inserts a new span at position 0, all subsequent positional comparisons will report mismatches even though only one span was added.

- **Decision**: `ReplayEngine.replay` is pure (no I/O, no side effects). **Why**: Replay should be safe to call multiple times, in tests, in read-only contexts, and concurrently. Side effects would break this guarantee. **Tradeoff**: If replay ever needs to simulate tool effects (e.g. to verify that a replayed plan would succeed against a live environment), a new, explicitly stateful replay variant would be needed.

- **Decision**: Token and cost metrics are read from `span.attributes` with integer/float coercion and a default of 0 when absent. **Why**: Attribute presence is optional — not all LLM spans may have cost instrumentation. Defaulting to 0 prevents `KeyError` exceptions during analysis of traces from partially instrumented code paths. **Tradeoff**: Missing attributes are silently treated as zero, which can make aggregated metrics appear lower than actual values.

---

## Scaling concerns

- `analyze` iterates all spans once (O(n) after sorting, which is O(n log n)). For traces with thousands of spans, this is fast (milliseconds).
- `detect_divergence` is O(n) in span count after sorting. For very large traces (tens of thousands of spans), it is still fast but the returned issue list could itself be large.
- `load_trace` reads the entire JSON file into memory before parsing. Very large trace files (hundreds of MB) will cause memory pressure. There is no streaming parser.
- `AnalysisReport` stores the full `timeline` list in memory. For a trace with 100,000 spans, this is a list of 100,000 `SpanSummary` objects.
- `ReplayEngine` holds a reference to the full `Trace`. Multiple `ReplayEngine` instances for the same trace share the same underlying `spans` tuple without copying (tuple is immutable), so there is no redundant memory usage.

---

## Future improvements

- **Streaming trace loading**: Replace `json.loads` in `load_trace` with a streaming JSON parser (e.g. `ijson`) to support large trace files without loading everything into RAM.
- **Alignment-based divergence detection**: Implement an LCS (Longest Common Subsequence) based diff for `detect_divergence` so that inserted or deleted spans are correctly attributed rather than causing cascading false positives.
- **Per-span cost breakdown in `AnalysisReport`**: Add a `SpanCostSummary` dataclass that pairs each LLM `SpanSummary` with its token counts and cost, and include it in `AnalysisReport` for drill-down analysis.
- **Export to standard formats**: Add `to_dict()` and `to_json()` methods to `AnalysisReport` for integration with dashboards, alerting systems, and cost tracking pipelines.
- **Flamegraph-style timeline rendering**: Add a text or HTML renderer for the `timeline` list that displays span durations as proportional bars, making it easier to identify bottlenecks visually.

---

## Usage examples

**Load and analyze a recorded trace:**

```python
from llm_agents.core.replay_analysis import load_trace, analyze

trace = load_trace("traces/agent_run_20260529.json")
report = analyze(trace)

print(f"Trace ID: {report.trace_id}")
print(f"Total spans: {report.span_count}")
print(f"LLM calls: {report.llm_call_count}")
print(f"Tool calls: {report.tool_call_count}")
print(f"Errors: {report.error_count}")
print(f"Total duration: {report.total_duration_s:.2f}s")
print(f"Prompt tokens: {report.total_prompt_tokens}")
print(f"Cost (USD): ${report.total_cost_usd:.4f}")

if report.errors:
    print("Errors encountered:")
    for err in report.errors:
        print(f"  {err}")
```

**Replay a trace for debugging:**

```python
from llm_agents.core.replay_analysis import load_trace, ReplayEngine

trace = load_trace("traces/failed_run.json")
engine = ReplayEngine(trace)
summaries = engine.replay()

for summary in summaries:
    status_marker = "[ERROR]" if summary.status.value == "error" else "[OK]   "
    print(f"{status_marker} {summary.name:40s} {summary.duration_s:.3f}s  [{summary.kind.value}]")
```

**Regression test: detect divergence between two runs:**

```python
from llm_agents.core.replay_analysis import load_trace, detect_divergence

baseline = load_trace("traces/baseline.json")
candidate = load_trace("traces/candidate.json")

issues = detect_divergence(recorded=baseline, fresh=candidate)
if issues:
    print("Divergence detected:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("No divergence detected. Traces match.")
```
