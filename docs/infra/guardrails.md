# guardrails

Module path: `src/llm_agents/infra/guardrails/`

## Overview

The guardrails module provides a composable, layered safety filtering system for LLM inputs and outputs. It defines a `Guard` Protocol that any checking function can satisfy, a set of built-in guard implementations covering regex blocking, keyword blocking, pattern redaction, and embedding-based similarity filtering, and a `GuardrailChain` that runs multiple guards in sequence and stops at the first violation. The design is intentionally lightweight by default — regex and keyword guards require no model inference — while remaining extensible to more sophisticated backends such as NVIDIA NeMo Guardrails via the `EmbeddingFilter` hook. The module produces a `GuardResult` for every check, carrying the (possibly redacted) text, the action taken, and a human-readable violation description, so that callers can audit, log, or escalate policy violations without parsing raw text.

---

## Public API

Import everything from `llm_agents.infra.guardrails`.

### Exported symbols

| Symbol | Kind | Description |
|---|---|---|
| `GuardAction` | StrEnum | Terminal action of a guardrail check: `PASS`, `BLOCK`, `REDACT`. |
| `GuardResult` | frozen dataclass | Full outcome of a guard check or chain run. |
| `Guard` | Protocol | Structural interface requiring `check(text: str) -> GuardResult`. |
| `RegexFilter` | class | Blocks text matching any supplied regex pattern. |
| `KeywordFilter` | class | Blocks text containing any listed keyword (case-insensitive). |
| `RedactFilter` | class | Replaces matched patterns with `[REDACTED]` (REDACT action, not BLOCK). |
| `EmbeddingFilter` | class | Blocks text when a caller-provided scorer returns similarity below a threshold. |
| `GuardrailChain` | class | Applies an ordered list of guards; stops at first BLOCK or REDACT. |

### `GuardAction` (StrEnum)

| Value | Meaning |
|---|---|
| `PASS` | Text is compliant; no action required. |
| `BLOCK` | Text is non-compliant; caller should discard or replace the output. |
| `REDACT` | Text was modified; the `GuardResult.text` field carries the sanitized version. |

### `GuardResult` (frozen dataclass)

```python
@dataclass(frozen=True)
class GuardResult:
    passed: bool
    action: GuardAction
    text: str
    violation_detail: str | None = None
```

| Class method | Signature | Description |
|---|---|---|
| `pass_` | `(text: str) -> GuardResult` | Convenience constructor for PASS results. |
| `block` | `(text: str, detail: str) -> GuardResult` | Convenience constructor for BLOCK results. |
| `redact` | `(text: str, detail: str) -> GuardResult` | Convenience constructor for REDACT results. |

`passed` is `True` only when `action == GuardAction.PASS`. `text` contains the original text for PASS/BLOCK results, and the redacted text for REDACT results.

### `Guard` (Protocol)

```python
@runtime_checkable
class Guard(Protocol):
    def check(self, text: str) -> GuardResult: ...
```

Any object with a matching `check` method satisfies this interface without inheriting from it. Guards must never raise; they must always return a `GuardResult`.

### `RegexFilter`

```python
class RegexFilter
    def __init__(
        self,
        patterns: list[str],
        flags: int = 0,
        detail: str = "Blocked pattern matched: {match}",
    ) -> None
```

Compiles all patterns at construction. `check(text)` returns BLOCK on the first pattern match, with the matched substring interpolated into `detail` via `{match}`. Returns PASS if no pattern matches.

### `KeywordFilter`

```python
class KeywordFilter
    def __init__(self, keywords: list[str]) -> None
```

Lowercases all keywords at construction. `check(text)` returns BLOCK on the first keyword found in the lowercased text. Returns PASS if no keyword is present. Case-insensitive by design; there is no flag to make it case-sensitive.

### `RedactFilter`

```python
class RedactFilter
    def __init__(
        self,
        patterns: list[str],
        flags: int = re.IGNORECASE,
        marker: str = "[REDACTED]",
    ) -> None
```

Compiles all patterns at construction (default `re.IGNORECASE`). `check(text)` applies all patterns via `re.subn` and accumulates replacements. Returns REDACT with the modified text if any match was made; returns PASS otherwise.

### `EmbeddingFilter`

```python
class EmbeddingFilter
    def __init__(
        self,
        scorer: Callable[[str], float],
        threshold: float = 0.5,
    ) -> None
```

`check(text)` calls `scorer(text)` and returns BLOCK if the returned float is below `threshold`, PASS otherwise. The `scorer` is fully caller-supplied; the filter class does not perform any embedding computation. Default `threshold` is `0.5`.

### `GuardrailChain`

```python
class GuardrailChain
    def __init__(
        self,
        guards: list[Any],
        on_violation: Callable[[GuardResult], None] | None = None,
    ) -> None
```

| Method | Signature | Description |
|---|---|---|
| `run` | `(text: str) -> GuardResult` | Run all guards in order. Stops and returns the first BLOCK or REDACT result. Returns PASS if all guards pass. |

The `on_violation` callback is invoked with the non-passing `GuardResult` immediately before returning, enabling audit logging without modifying the return value or flow.

---

## Architecture

### Conceptual view

```
Input text (LLM output or user input)
    |
    | chain.run(text)
    v
GuardrailChain
    |
    +-- guard[0].check(text)
    |       |
    |       +-- PASS   -> proceed with (possibly updated) text
    |       +-- BLOCK  -> on_violation(result), return result immediately
    |       +-- REDACT -> on_violation(result), return result immediately
    |
    +-- guard[1].check(text)  (if guard[0] passed)
    |       ...
    |
    +-- guard[N].check(text)
    |
    +-- All passed -> return GuardResult.pass_(final_text)

Guard implementations:
    RegexFilter    -> compiled regex patterns -> BLOCK on match
    KeywordFilter  -> lowercased keywords     -> BLOCK on substring
    RedactFilter   -> compiled regex patterns -> REDACT (in-place replace)
    EmbeddingFilter-> scorer: (str)->float    -> BLOCK if score < threshold
```

### Data flow

1. The caller instantiates one or more guard objects and passes them as an ordered list to `GuardrailChain`.
2. `chain.run(text)` sets `current_text = text` and iterates `self._guards`.
3. For each guard: `result = guard.check(current_text)`.
   - If `result.action` is `PASS`: update `current_text = result.text` (in case a future redact-capable guard modified it) and continue to the next guard.
   - If `result.action` is `BLOCK` or `REDACT`: call `self._on_violation(result)` if set, then return `result` immediately. The remaining guards are not evaluated.
4. If all guards return `PASS`, return `GuardResult.pass_(current_text)` where `current_text` is the final text after any redactions applied by `RedactFilter` guards earlier in the chain.

Note: currently `RegexFilter` and `KeywordFilter` do not modify `text` on PASS (they return the original `text`), so the pass-through `current_text = result.text` is a no-op for those guards. `RedactFilter` does modify text on REDACT and stops the chain; it does not modify and continue. A chain that needs to apply multiple redactions requires multiple `RedactFilter` guards or patterns concatenated into one.

### Key abstractions

**`GuardAction` (StrEnum):** Three distinct outcomes cleanly separate the caller's response strategies: PASS requires no action; BLOCK requires the caller to discard or replace the LLM output; REDACT means the output was salvaged and the caller should use `result.text` instead of the original. StrEnum makes the value directly serializable to JSON for audit logging.

**`GuardResult` (frozen dataclass):** Immutable so it can be safely passed to callbacks, stored in audit logs, or returned from API endpoints without risk of downstream mutation. The `text` field carries the (possibly modified) text so that callers do not need to maintain a separate "safe text" variable alongside the result.

**`Guard` Protocol:** Structural typing allows any callable object with a `check(text) -> GuardResult` method to participate in a chain without importing from this module. This is critical for integrating third-party guard libraries or ML-based classifiers that cannot take a dependency on `llm_agents`.

**`EmbeddingFilter` scorer delegation:** The filter class does not implement any embedding model. It accepts a `Callable[[str], float]` that the caller provides — this could be a cosine similarity against a reference embedding, a classifier logit, or a stub returning 1.0. This design keeps the guard module free of heavy ML dependencies while still supporting semantic similarity filtering.

**`GuardrailChain` early exit:** Stopping at the first violation is the correct security posture: once a BLOCK is detected, evaluating further guards on the same text is wasteful and potentially misleading. The chain design also means that the order of guards matters — cheaper guards (keyword lookup) should be placed before expensive ones (embedding model inference).

---

## Design decisions and tradeoffs

- **Decision:** BLOCK and REDACT both stop the chain immediately. **Why:** A chain that continued after a BLOCK could allow a later guard to overrule the block, which violates the principle of least privilege. **Tradeoff:** A use case that needs to apply multiple redactions in one pass requires either a single `RedactFilter` with all patterns, or a chain where each guard processes the already-redacted output. The current implementation does not support chaining after a REDACT.

- **Decision:** `KeywordFilter` is always case-insensitive. **Why:** Case-insensitive matching is the safe default for prohibited content; a case-sensitive keyword filter would miss trivial evasion (e.g., "PaSsWoRd"). **Tradeoff:** No option to opt into case-sensitive matching. Callers that need case-sensitive keyword matching must use `RegexFilter` without `re.IGNORECASE`.

- **Decision:** `GuardResult.text` for BLOCK results contains the original (unmodified) text. **Why:** On a block, the caller is expected to discard the text entirely; providing the original text (rather than an empty string) preserves the audit record. **Tradeoff:** Callers that carelessly use `result.text` without checking `result.passed` or `result.action` may inadvertently use blocked content.

- **Decision:** `on_violation` is an optional synchronous callback rather than a hook list or event system. **Why:** Simplicity. The single callback covers the primary use case (audit logging) without the overhead of an event bus. **Tradeoff:** Only one violation handler per chain. Multiple handlers require wrapping in a combined function at the call site.

- **Decision:** `EmbeddingFilter` threshold defaults to `0.5`. **Why:** Midpoint of the [0.0, 1.0] range, usable as a starting point when the scorer's distribution is unknown. **Tradeoff:** The appropriate threshold is highly scorer-dependent. A poorly calibrated scorer with a 0.5 threshold will produce many false positives or false negatives. Callers must tune the threshold for their specific scorer.

---

## Scaling concerns

- **`RegexFilter` and `RedactFilter` compilation:** Patterns are compiled at construction time, so `check()` calls are fast (compiled `re.search`/`re.subn`). Under very high text volume (millions of checks/second), Python's `re` engine is the bottleneck. Consider `re2` or PCRE2 via a C extension for production throughput.

- **`EmbeddingFilter` scorer latency:** If the scorer calls a local ML model, each `check()` is an inference call. Placing `EmbeddingFilter` last in the chain (after cheaper keyword/regex guards have already filtered most violations) minimizes unnecessary inference calls.

- **`KeywordFilter` linear scan:** `check()` performs a linear scan of the keyword list against the lowercased text. For very large keyword lists (>10,000 keywords), building an Aho-Corasick automaton at construction time would reduce check time from O(K × N) to O(N) where K is the number of keywords and N is the text length.

- **No async support:** All guards are synchronous. If the `EmbeddingFilter` scorer calls an async service (e.g., an HTTP embedding endpoint), it must be wrapped with `asyncio.get_event_loop().run_until_complete`, which blocks the event loop. An async `Guard` Protocol variant would be needed for production async scoring.

- **No caching in `EmbeddingFilter`:** The same text can be scored multiple times if it passes through multiple chains. A per-session or per-request scoring cache would eliminate redundant inference calls.

---

## Future improvements

- **Async `Guard` Protocol variant:** Define `AsyncGuard` with `async def check(self, text: str) -> GuardResult` and add `async def run(self, text: str) -> GuardResult` to `GuardrailChain`, enabling non-blocking integration with HTTP-based scoring services.

- **Aho-Corasick `KeywordFilter`:** Replace the linear scan with a compiled Aho-Corasick automaton (e.g., via the `ahocorasick` package) for O(N) multi-keyword matching, dramatically reducing check latency for large keyword lists.

- **Chain continuation after REDACT:** Add a `continue_after_redact: bool` option to `GuardrailChain` that, instead of stopping on REDACT, updates `current_text` with the redacted text and continues evaluating subsequent guards. This would allow multiple redactions in a single pass.

- **NeMo Guardrails adapter:** Implement a `NeMoGuard` class that satisfies the `Guard` Protocol and delegates to the NVIDIA NeMo Guardrails runtime, providing access to its Colang-based policy language and trained classifiers without requiring the main module to import NeMo.

- **Per-guard metadata in result:** Extend `GuardResult` with a `guard_name: str | None` field populated by `GuardrailChain` so that audit logs identify which specific guard in a chain triggered the violation, not just the final result.

- **Violation rate metrics:** Integrate with the observability module by adding an optional `on_violation` callback to `GuardrailChain` that increments a `MetricsRegistry` counter keyed on `guard_name` and `action`, providing Prometheus-scrapable policy violation rates.

---

## Usage examples

### Keyword and regex blocking

```python
import re
from llm_agents.infra.guardrails import GuardrailChain, KeywordFilter, RegexFilter

chain = GuardrailChain([
    KeywordFilter(["secret", "internal", "confidential"]),
    RegexFilter([r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"], flags=re.IGNORECASE),
])

result = chain.run("Here is your card: 4111 1111 1111 1111")
if not result.passed:
    print(f"BLOCKED: {result.violation_detail}")
    # BLOCKED: Blocked pattern matched: 4111 1111 1111 1111
```

### Redacting sensitive patterns

```python
from llm_agents.infra.guardrails import GuardrailChain, RedactFilter

chain = GuardrailChain([
    RedactFilter(
        patterns=[r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"],
        marker="[EMAIL REDACTED]",
    ),
])

result = chain.run("Contact us at user@example.com for support.")
print(result.action)   # redact
print(result.text)     # "Contact us at [EMAIL REDACTED] for support."
```

### Embedding-based semantic filtering with audit callback

```python
from llm_agents.infra.guardrails import GuardrailChain, EmbeddingFilter, GuardResult

def my_scorer(text: str) -> float:
    # Replace with a real cosine similarity against a reference embedding
    return 0.8 if "agent" in text.lower() else 0.2

def audit(result: GuardResult) -> None:
    print(f"VIOLATION [{result.action}]: {result.violation_detail}")

chain = GuardrailChain(
    guards=[EmbeddingFilter(scorer=my_scorer, threshold=0.5)],
    on_violation=audit,
)

result = chain.run("This response talks about the weather.")
# VIOLATION [block]: Embedding similarity 0.200 below threshold 0.500
print(result.passed)  # False
```
