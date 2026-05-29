# inference_routing

Module path: `src/llm_agents/infra/inference_routing/`

## Overview

The inference routing module provides a uniform async interface for dispatching LLM completion requests to one or more backend providers with automatic retry, exponential backoff, and ordered failover. Its purpose is to decouple the rest of the agent system from provider-specific details: callers construct an `LLMRequest` and call `Router.complete()`; the router selects a provider from a `RoutingPolicy`, handles transient failures transparently, and returns an `LLMResponse`. Every individual provider attempt is traced as an `SpanKind.LLM` span; the outer routing call is traced as an `SpanKind.AGENT` span. The module wires itself to the observability subsystem by registering `bridge_span` as the collector export hook, so request counts, latency, token usage, and cost metrics are updated automatically on each completed call.

---

## Public API

Import everything from `llm_agents.infra.inference_routing`.

### Exported symbols

| Symbol | Kind | Description |
|---|---|---|
| `LLMRequest` | dataclass | Uniform request payload sent to any provider. |
| `LLMResponse` | frozen dataclass | Immutable response returned by a provider. |
| `Candidate` | dataclass | A `(provider, model)` pair in a routing policy. |
| `RoutingPolicy` | dataclass | Describes candidates, retry count, and backoff parameters. |
| `AllProvidersFailedError` | exception | Raised when every candidate and all retries are exhausted. |
| `Provider` | Protocol | Structural interface that any async LLM adapter must satisfy. |
| `FakeProvider` | class | In-memory test double that replays preset responses or raises. |
| `Router` | class | Async LLM router with retry, backoff, and failover. |

### `LLMRequest` (dataclass fields)

| Field | Type | Default | Description |
|---|---|---|---|
| `model` | `str` | required | Target model identifier. |
| `messages` | `list[dict[str, str]]` | required | Chat messages in OpenAI format. |
| `max_tokens` | `int` | `512` | Maximum generation tokens. |
| `temperature` | `float` | `0.0` | Sampling temperature. |
| `extra` | `dict[str, Any]` | `{}` | Provider-specific pass-through parameters. |

### `LLMResponse` (frozen dataclass fields)

| Field | Type | Default | Description |
|---|---|---|---|
| `model` | `str` | required | Model that generated the response. |
| `content` | `str` | required | Generated text content. |
| `prompt_tokens` | `int` | required | Prompt tokens consumed. |
| `completion_tokens` | `int` | required | Completion tokens generated. |
| `latency_s` | `float` | required | Wall-clock call duration in seconds. |
| `cost_usd` | `float` | `0.0` | Estimated cost in USD. |
| `provider_name` | `str` | `""` | Name of the provider that served the request. |

### `Candidate` (dataclass fields)

| Field | Type | Description |
|---|---|---|
| `provider` | `Provider` | The async provider adapter. |
| `model` | `str` | Model override applied when this candidate is tried. |

### `RoutingPolicy` (dataclass fields)

| Field | Type | Default | Description |
|---|---|---|---|
| `candidates` | `list[Candidate]` | required | Ordered list of candidates to try. |
| `max_retries` | `int` | `2` | Additional attempts per candidate on failure. |
| `backoff_base_s` | `float` | `0.1` | Base delay for exponential backoff between retries. |

Total attempts per candidate = `max_retries + 1`. Backoff delay on attempt `n` = `backoff_base_s * 2 ** n`.

### `Provider` (Protocol)

```python
@runtime_checkable
class Provider(Protocol):
    name: str
    async def complete(self, request: LLMRequest) -> LLMResponse: ...
```

Any class with a `name: str` attribute and a matching `complete` coroutine satisfies this interface without inheriting from it. `runtime_checkable` allows `isinstance(obj, Provider)` checks.

### `FakeProvider`

```python
class FakeProvider
    def __init__(
        self,
        name: str,
        responses: list[LLMResponse | BaseException],
    ) -> None
```

| Attribute/Method | Description |
|---|---|
| `name` | Provider name string. |
| `call_count` | Number of times `complete` was called. |
| `complete(request)` | Returns the next response in the sequence or raises if it is an exception. Last item repeats when sequence is exhausted. |

### `Router`

```python
class Router
    def __init__(
        self,
        policy: RoutingPolicy,
        export_hook: Callable[[FinishedSpan], None] | None = bridge_span,
    ) -> None
```

| Method | Signature | Description |
|---|---|---|
| `complete` | `async (request: LLMRequest) -> LLMResponse` | Route request through the policy; raise `AllProvidersFailedError` if all fail. |

### `AllProvidersFailedError`

```python
class AllProvidersFailedError(Exception)
    errors: list[BaseException]  # one per failed attempt, chronological
```

---

## Architecture

### Conceptual view

```
Caller
  |
  | await router.complete(LLMRequest)
  v
Router
  |-- opens outer span (SpanKind.AGENT, name="routing")
  |
  +-- for each Candidate in RoutingPolicy.candidates:
  |     +-- for attempt in range(max_retries + 1):
  |           |-- opens inner span (SpanKind.LLM, name="llm_call")
  |           |-- replaces request.model with candidate.model
  |           |-- await candidate.provider.complete(request)
  |           |     |
  |           |     +-- success: attach attributes, return LLMResponse
  |           |     +-- failure: set ERROR status, sleep backoff, next attempt
  |           |-- closes inner span -> InMemoryCollector -> export_hook(bridge_span)
  |
  +-- all candidates exhausted -> raise AllProvidersFailedError(all_errors)
```

### Data flow

1. The caller creates a `RoutingPolicy` with an ordered list of `Candidate` objects. Each candidate pairs a `Provider` adapter with a model name.
2. `Router.complete(request)` opens an outer `SpanKind.AGENT` span named `"routing"` with a `policy_candidates` attribute.
3. The router iterates candidates in order. For each candidate, it iterates up to `max_retries + 1` attempts.
4. Each attempt opens an inner `SpanKind.LLM` span named `"llm_call"` with `model` and `provider` attributes.
5. The request's `model` field is overridden with `candidate.model` via `dataclasses.replace` (non-mutating).
6. `candidate.provider.complete(req)` is awaited. On success, response attributes (`prompt_tokens`, `completion_tokens`, `latency_s`, `cost_usd`) are attached to the inner span, both spans are marked `OK`, and the `LLMResponse` is returned immediately.
7. On exception, the inner span is marked `ERROR`, the error is appended to `all_errors`, and the router sleeps `backoff_base_s * 2 ** attempt` seconds before the next attempt (no sleep after the final attempt for a candidate).
8. When all candidates and retries are exhausted, the outer span is marked `ERROR` and `AllProvidersFailedError(all_errors)` is raised.
9. When each inner span closes, `InMemoryCollector.add()` fires the `bridge_span` hook, which updates the `MetricsRegistry` counters and histograms.

### Key abstractions

**`Provider` Protocol:** Structural typing (no inheritance required) means any existing OpenAI, Anthropic, or local model client can be wrapped in a thin adapter without importing from this module. `runtime_checkable` enables `isinstance` guards at integration points.

**`Candidate`:** Separates the provider identity from the model selection. This allows the same provider instance to appear as two candidates with different models (e.g., try `gpt-4o` first, fall back to `gpt-4o-mini` on the same OpenAI client).

**`RoutingPolicy`:** A pure data object describing routing behavior. This makes policies easy to construct from configuration files, serialize, or pass between components without coupling them to the `Router` implementation.

**`FakeProvider` playback sequence:** Using an ordered list of responses/exceptions rather than a single fixed response allows tests to simulate realistic failure-then-success scenarios (e.g., two rate-limit errors followed by a successful response) without needing to mock asyncio internals.

---

## Design decisions and tradeoffs

- **Decision:** Outer (AGENT) and inner (LLM) spans are nested. **Why:** The outer span captures the total routing duration including all retries; inner spans capture individual provider call latency. This gives operators two levels of detail in the trace viewer without custom instrumentation. **Tradeoff:** Two span objects are allocated per attempt. Under very high call volume (thousands of concurrent routing calls), this adds allocation pressure.

- **Decision:** `bridge_span` is registered as the default `export_hook` in `Router.__init__`. **Why:** Ensures that metrics are populated automatically for every `Router` instance without requiring callers to configure the observability pipeline manually. **Tradeoff:** Tests that create a `Router` instance will silently overwrite any hook previously registered on the singleton collector. Tests must pass `export_hook=None` to avoid this.

- **Decision:** `dataclasses.replace(request, model=candidate.model)` is used to override the model. **Why:** `LLMRequest` is a mutable dataclass but the router must not mutate the caller's request object. `replace` creates a shallow copy with the model field overridden. **Tradeoff:** Shallow copy means `extra` dict is shared between the original and the copy; mutations to `extra` in the provider would be visible to the caller.

- **Decision:** Backoff sleep uses `asyncio.sleep`. **Why:** Non-blocking; yields control to the event loop so other coroutines can run during the wait. **Tradeoff:** No jitter is applied to the backoff delay. Under simultaneous failures (e.g., a cloud provider rate limit that hits all concurrent callers at once), all callers will retry at the same offset times, producing a thundering herd on recovery.

- **Decision:** `AllProvidersFailedError` accumulates all errors in a list. **Why:** Preserves the full error history for debugging; callers can inspect which provider failed and with what error at each attempt. **Tradeoff:** In long retry chains the error list can be large; error objects may hold references to large exception state.

---

## Scaling concerns

- **Concurrency:** Each `Router.complete` call is independent; many can run concurrently. The bottleneck is typically the provider rate limit, not the router itself.

- **Backoff without jitter:** Under simultaneous provider failures, all concurrent `Router` instances will wake from backoff sleep at the same time. Add jitter (`random.uniform(0, backoff_base_s)`) to spread the load.

- **Single export hook slot:** `InMemoryCollector` has one hook slot. Registering multiple `Router` instances (each with `export_hook=bridge_span`) will redundantly re-register the same function. The last registration wins; if different hooks are needed per router, the current design cannot support this without changes to the collector.

- **Span allocation:** Every `Router.complete` call allocates two `_SpanContext` objects and two `FinishedSpan` objects (plus any retry spans). High call rates (>10,000 calls/second) will produce significant GC pressure.

- **No circuit breaker:** There is no circuit-breaker pattern. A provider that consistently fails will be retried (with backoff) on every call until `max_retries` is exhausted. A circuit breaker would short-circuit retries to a failed provider and allow faster failover.

---

## Future improvements

- **Jitter in backoff:** Add `random.uniform(0, backoff_base_s)` to each sleep duration to spread retry load under simultaneous failures.

- **Circuit breaker:** Track per-provider failure rates in `Router` state and skip a provider for a configurable window (e.g., 30 seconds) after a threshold of consecutive failures.

- **Multiple export hooks:** Extend `InMemoryCollector` to support a list of hooks rather than a single slot, so multiple `Router` instances can each register a hook without overwriting each other.

- **Streaming support:** Add a `stream_complete` method to the `Provider` Protocol and `Router` that yields response tokens incrementally, supporting streaming use cases.

- **Priority weights:** Add a `weight: float` field to `Candidate` and implement weighted round-robin selection rather than strict ordered failover, enabling load balancing across providers at the same priority tier.

- **Timeout per attempt:** Add a `timeout_s: float` field to `RoutingPolicy` and wrap each `provider.complete` call with `asyncio.wait_for`, so a hanging provider does not block the entire routing call indefinitely.

---

## Usage examples

### Basic routing with a single provider

```python
from llm_agents.infra.inference_routing import (
    LLMRequest, Candidate, RoutingPolicy, Router, FakeProvider, LLMResponse
)

fake = FakeProvider(
    name="openai",
    responses=[LLMResponse(
        model="gpt-4o", content="Hello!", prompt_tokens=10,
        completion_tokens=5, latency_s=0.3, cost_usd=0.0001,
    )],
)

policy = RoutingPolicy(candidates=[Candidate(provider=fake, model="gpt-4o")])
router = Router(policy)

request = LLMRequest(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Say hello."}],
)
response = await router.complete(request)
print(response.content)  # "Hello!"
```

### Failover: primary provider fails, secondary succeeds

```python
from llm_agents.infra.inference_routing import (
    LLMRequest, Candidate, RoutingPolicy, Router, FakeProvider, LLMResponse
)

primary = FakeProvider("primary", responses=[RuntimeError("rate limited")])
secondary = FakeProvider(
    "secondary",
    responses=[LLMResponse("gpt-4o-mini", "Hi!", 8, 4, 0.15, 0.00005)],
)

policy = RoutingPolicy(
    candidates=[
        Candidate(provider=primary, model="gpt-4o"),
        Candidate(provider=secondary, model="gpt-4o-mini"),
    ],
    max_retries=0,
    backoff_base_s=0.0,
)
router = Router(policy, export_hook=None)
response = await router.complete(LLMRequest("gpt-4o", [{"role": "user", "content": "Hi"}]))
print(response.provider_name)  # "secondary"
```

### Handling complete failure

```python
from llm_agents.infra.inference_routing import (
    AllProvidersFailedError, LLMRequest, Candidate, RoutingPolicy, Router, FakeProvider
)

broken = FakeProvider("broken", responses=[RuntimeError("service down")])
policy = RoutingPolicy(
    candidates=[Candidate(provider=broken, model="gpt-4o")],
    max_retries=1,
    backoff_base_s=0.01,
)
router = Router(policy, export_hook=None)

try:
    await router.complete(LLMRequest("gpt-4o", [{"role": "user", "content": "ping"}]))
except AllProvidersFailedError as exc:
    print(f"Failed after {len(exc.errors)} attempts: {exc.errors[-1]}")
```
