# cost_latency_optimization

Module path: `src/llm_agents/infra/cost_latency_optimization/`

## Overview

The cost_latency_optimization module reduces the monetary cost and wall-clock latency of LLM calls through three complementary mechanisms: a budget tracker, an in-memory completion cache, and a concurrent request batcher. The `BudgetTracker` accumulates token counts and estimated cost across a session so that agents and orchestrators can make data-driven decisions about model selection or early termination. The `CompletionCache` stores completed responses by a deterministic hash of the request parameters and serves cache hits without touching the network, eliminating latency and cost entirely for repeated or near-identical queries. The `Batcher` dispatches a list of independent LLM requests concurrently via `asyncio.gather`, saturating available concurrency rather than waiting for each request to finish sequentially. The three components are designed to be composed freely: a cache wraps a router, a batcher wraps a router, and a budget tracker consumes responses from any source.

Additionally the module owns the **pluggable content-hash deduplication store** abstraction used by `data/ingestion` and `rag/indexing`. The `DeduplicationStore` Protocol defines a minimal set/persist interface. `InMemoryDeduplicationStore` is the default (fast, zero-config, state lost on restart). `SQLiteDeduplicationStore` is the durable variant (stdlib `sqlite3`, hashes survive process restarts), enabling incremental ingestion and indexing jobs that do not re-embed unchanged content on cold start.

---

## Public API

Import everything from `llm_agents.infra.cost_latency_optimization`.

### Exported symbols

| Symbol | Kind | Description |
|---|---|---|
| `BudgetReport` | frozen dataclass | Immutable snapshot of accumulated token usage and cost. |
| `BudgetTracker` | class | Accumulates token counts and cost from `LLMResponse` objects. |
| `CompletionCache` | class | In-memory LRU cache with TTL expiry for LLM completions. |
| `Batcher` | class | Concurrent LLM request dispatcher using `asyncio.gather`. |
| `DeduplicationStore` | Protocol | Interface for pluggable content-hash deduplication backends. |
| `InMemoryDeduplicationStore` | class | Default in-memory dedup store; state lost on restart. |
| `SQLiteDeduplicationStore` | class | Durable SQLite-backed dedup store; state persists across restarts. |

### `BudgetReport` (frozen dataclass fields)

| Field | Type | Description |
|---|---|---|
| `prompt_tokens` | `int` | Total prompt tokens across all tracked calls. |
| `completion_tokens` | `int` | Total completion tokens across all tracked calls. |
| `total_tokens` | `int` | `prompt_tokens + completion_tokens`. |
| `cost_usd` | `float` | Accumulated estimated cost in USD. |
| `call_count` | `int` | Number of `LLMResponse` objects tracked. |

### `BudgetTracker`

```python
class BudgetTracker
    def __init__(self) -> None
```

| Method | Signature | Description |
|---|---|---|
| `track` | `(response: LLMResponse) -> None` | Accumulate token counts and cost from `response`. |
| `report` | `() -> BudgetReport` | Return an immutable snapshot of current totals. |
| `reset` | `() -> None` | Zero all accumulators. Call to start a new tracking period. |

### `CompletionCache`

```python
class CompletionCache
    def __init__(
        self,
        ttl_s: float = 300.0,
        max_size: int | None = None,
    ) -> None
```

| Method | Signature | Description |
|---|---|---|
| `get` | `(request: LLMRequest) -> LLMResponse \| None` | Return the cached response, or `None` on miss or expiry. |
| `set` | `(request: LLMRequest, response: LLMResponse) -> None` | Store a response. Evicts the LRU entry if `max_size` is exceeded. |
| `clear` | `() -> None` | Remove all cached entries. |
| `cached_complete` | `async (request: LLMRequest, router: Router, *, force_refresh: bool = False) -> LLMResponse` | Return from cache or route the request and cache the result. |

Cache key fields: `model`, `messages`, `max_tokens`, `temperature`. The `extra` field is excluded from the key by design.

### `Batcher`

```python
class Batcher
    def __init__(self, router: Router) -> None
```

| Method | Signature | Description |
|---|---|---|
| `batch_complete` | `async (requests: list[LLMRequest]) -> list[LLMResponse \| BaseException]` | Dispatch all requests concurrently. Returns results in input order. Exceptions are not re-raised. |

### `DeduplicationStore`

```python
class DeduplicationStore(Protocol):  # @runtime_checkable
    def add(self, hash: str) -> None: ...
    def add_batch(self, hashes: list[str]) -> None: ...
    def __contains__(self, hash: str) -> bool: ...
    def reset(self) -> None: ...
    def __len__(self) -> int: ...
```

Any object that implements all five methods satisfies the protocol without inheritance.
`isinstance(obj, DeduplicationStore)` works at runtime.

| Method | Description |
|---|---|
| `add(hash)` | Record one hash.  Commits immediately in `SQLiteDeduplicationStore`. |
| `add_batch(hashes)` | Record all hashes in one operation.  Empty list is a no-op.  `SQLiteDeduplicationStore` issues one `executemany` + one `commit`, regardless of list length. |
| `__contains__(hash)` | Return `True` if hash has been added since the last `reset`. |
| `reset()` | Clear all stored hashes. |
| `__len__()` | Return the number of distinct hashes stored. |

### `InMemoryDeduplicationStore`

```python
class InMemoryDeduplicationStore:
    def __init__(self) -> None: ...
```

Backed by a `set[str]`. State is lost when the process exits. This is the default used
when no explicit `dedup_store` is provided to `IngestionPipeline` or `Indexer`.

### `SQLiteDeduplicationStore`

```python
class SQLiteDeduplicationStore:
    def __init__(self, path: str | Path) -> None: ...
```

Backed by a SQLite database file (stdlib `sqlite3`). `add()` commits one hash
immediately. `add_batch()` wraps all inserts in a single transaction (one `commit`),
reducing write latency from O(N) to O(1) for bulk workloads. Hashes survive process
restarts. Pass `":memory:"` for an in-memory SQLite database (useful in tests).

Raises `sqlite3.OperationalError` if the directory containing `path` does not exist.

---

## Architecture

### Conceptual view

```
                          [BudgetTracker]
                               ^
                               | tracker.track(response)
                               |
[CompletionCache]          [Batcher]
    |                          |
    | cache hit -> return       | asyncio.gather(router.complete(...) * N)
    |                          |
    +-- cache miss -> [Router] <--+
                        |
                        | ordered failover + retry + backoff
                        v
                   [Provider(s)]
                  (network / API)
```

### Data flow

#### BudgetTracker

1. After each `router.complete(request)` or `cache.cached_complete(request, router)`, the caller passes the returned `LLMResponse` to `tracker.track(response)`.
2. `track` adds `response.prompt_tokens`, `response.completion_tokens`, and `response.cost_usd` to running accumulators and increments `_call_count`.
3. `tracker.report()` returns a frozen `BudgetReport` snapshot. The tracker's internal state is not reset; `report()` can be called repeatedly.
4. `tracker.reset()` zeroes all accumulators to start a new period.

#### CompletionCache

1. `cached_complete(request, router)` computes the MD5 hex digest of the JSON-serialized key fields (`model`, `messages`, `max_tokens`, `temperature`) to produce the cache key.
2. On cache hit (`get()` returns a response that has not expired): return immediately without calling the router.
3. On expiry or miss: call `router.complete(request)` to get a fresh response, then call `set(request, response)` to store it.
4. `set()` inserts the response into an `OrderedDict` with `expire_at = time.monotonic() + ttl_s`. If `max_size` is set, `popitem(last=False)` evicts the oldest (LRU) entry until the store is within bounds.
5. `get()` reads the entry, checks `time.monotonic() > expire_at`, and deletes expired entries on access. On a valid hit, `move_to_end(key)` promotes the entry to the most-recently-used position.
6. `force_refresh=True` bypasses the cache read but still writes the fresh response back.

#### Batcher

1. `batch_complete(requests)` returns immediately if `requests` is empty.
2. It builds a list of coroutines: `[router.complete(r) for r in requests]`.
3. `asyncio.gather(*coroutines, return_exceptions=True)` dispatches all coroutines concurrently. Individual failures are captured as exception objects in the result list rather than propagated.
4. The result list is returned in the same order as the input `requests` list.

### Key abstractions

**`BudgetReport` (frozen dataclass):** Immutable so it can be safely stored, logged, or returned from an API endpoint without risk of the tracker's subsequent `track()` calls mutating the snapshot. `total_tokens` is derived (`prompt_tokens + completion_tokens`) rather than separately accumulated, ensuring consistency.

**`CompletionCache._store` (OrderedDict):** An `OrderedDict` provides O(1) move-to-end (for LRU promotion) and O(1) popitem-from-front (for LRU eviction). A plain dict would not support ordered eviction. TTL expiry is checked lazily on `get()` access rather than via a background sweep thread, keeping the implementation single-threaded and event-loop friendly.

**Cache key via MD5 hash:** MD5 is used as a fast, non-cryptographic collision-resistant hash to produce a fixed-length string key. JSON serialization with `sort_keys=True` ensures that semantically equivalent requests (same fields in different insertion order) produce the same key. The `extra` field is excluded because it is intended for provider-specific parameters that callers are expected to manage separately via `force_refresh`.

**Batcher with `return_exceptions=True`:** Passing `return_exceptions=True` to `asyncio.gather` means that one failing request does not cancel or prevent the other concurrent requests from completing. The caller receives the full result list and can inspect each slot individually, which is essential for batch processing pipelines that need partial results.

---

## Design decisions and tradeoffs

- **Decision:** Cache expiry is lazy (checked on access) rather than background-thread-based. **Why:** Avoids the complexity of a background task that must be started, stopped, and coordinated with the event loop. **Tradeoff:** Expired entries occupy memory until they are accessed and evicted. A cache with `max_size=None` and a long TTL can accumulate stale entries indefinitely if not accessed.

- **Decision:** `BudgetTracker` is not thread-safe; intended for single asyncio task use. **Why:** Thread safety would require a lock on every `track()` call, adding overhead. Agents in this system are asyncio-based, so a per-task tracker is the natural model. **Tradeoff:** Sharing a single `BudgetTracker` across concurrent tasks (e.g., multiple `asyncio.gather` branches) produces race conditions. Each task should have its own tracker.

- **Decision:** MD5 is used for the cache key. **Why:** Fast hash function appropriate for a non-security context (cache key generation, not integrity verification). **Tradeoff:** There is a theoretical (negligible) collision probability; two different requests could map to the same key and one would incorrectly receive the other's cached response. In practice this is not an issue at expected cache sizes.

- **Decision:** `Batcher.batch_complete` uses `asyncio.gather` with no concurrency limit. **Why:** Simplicity; all requests are dispatched simultaneously. **Tradeoff:** A large batch (e.g., 1,000 requests) will open 1,000 concurrent connections, potentially exhausting provider rate limits or connection pool limits. Callers are responsible for batching appropriately sized groups.

- **Decision:** `force_refresh=True` on `cached_complete` bypasses the cache read but still writes back. **Why:** Allows callers to obtain a guaranteed-fresh response (e.g., after a model version change) while still populating the cache for subsequent callers. **Tradeoff:** If two concurrent callers both use `force_refresh=True` for the same request, both will issue provider calls and the second write will overwrite the first without any coordination.

- **Decision:** `DeduplicationStore` is defined in this module, not in `data/` or `rag/`. **Why:** Both `data/ingestion` and `rag/indexing` need identical deduplication semantics; placing the Protocol here avoids a cross-subsystem dependency and aligns with the `infra` layer's role as a shared utility layer consumed by all higher layers. Both consumers re-export the three names from their own `__init__` for caller convenience. **Tradeoff:** A caller who only uses `IngestionPipeline` must transitively depend on `infra/cost_latency_optimization` even if they never use caching or batching, though this is a lightweight stdlib-only module.

- **Decision:** `SQLiteDeduplicationStore.add()` commits after every single hash; `add_batch()` commits once for the whole list. **Why:** `add()` guarantees per-hash durability — a crash loses at most the current hash. `add_batch()` provides O(1) commit cost for bulk workloads at the cost of coarser durability (if the process crashes mid-batch, none of the batch's hashes are recorded, so the entire batch is re-processed on retry — which is the safe failure mode). `Indexer` uses `add_batch` after all vector-store upserts succeed, ensuring the two writes are consistent. **Tradeoff:** Callers who need per-hash durability (e.g. streaming one chunk at a time across a network boundary) should use `add()` directly.

---

## Scaling concerns

- **Cache memory:** With `max_size=None`, the cache grows unboundedly. Each `LLMResponse` object holds the full generated text string. Caching thousands of long-completion responses will consume significant memory. Always set `max_size` in production.

- **Cache key collision risk at scale:** MD5 produces a 128-bit key space. At cache sizes below 10 million entries the collision probability remains negligible, but above this scale a stronger hash or a full-equality check on collision should be considered.

- **Batcher concurrency:** `asyncio.gather` with a large batch issues all requests simultaneously. Most LLM APIs enforce per-minute and per-second token/request rate limits. Batches larger than the provider's burst limit will result in rate-limit errors on some requests, which will be returned as `BaseException` instances in the result list.

- **BudgetTracker accumulation:** The tracker has no overflow protection. Very long sessions with millions of calls will accumulate `float` values subject to floating-point precision degradation. The tracker should be periodically `reset()` or replaced with a fresh instance.

- **No distributed cache:** `CompletionCache` is in-process memory. Multiple worker processes or distributed nodes do not share a cache. A Redis-backed cache would be needed for multi-process deployments.

- **`SQLiteDeduplicationStore` write amplification:** Each `add()` call issues a separate `INSERT OR IGNORE` + `COMMIT`. For a document with 100 chunks, this is 100 file-system syncs. On spinning disk this can be a throughput bottleneck. `add_batch()` (see Future improvements) is the mitigation.

- **`SQLiteDeduplicationStore` unbounded growth:** The `hashes` table grows by one row per unique content hash and is never pruned. At one million hashes (32-byte strings + SQLite overhead ≈ ~100 bytes/row) the file is approximately 100 MB. Long-running ingestion jobs should schedule periodic `reset()` or use the planned TTL expiry feature.

---

## Future improvements

- **Async background TTL sweep:** Add an optional background `asyncio.Task` that scans the cache periodically for expired entries and evicts them proactively, preventing memory accumulation in low-traffic caches.

- **Concurrency limiter in Batcher:** Add a `max_concurrent: int` parameter to `batch_complete` implemented with `asyncio.Semaphore`, so large batches are dispatched in chunks rather than all at once.

- **Redis-backed cache:** Implement a `RemoteCompletionCache` class that uses an async Redis client for storage, enabling cache sharing across multiple process instances with server-side TTL enforcement.

- **Budget enforcement in BudgetTracker:** Add `cost_limit_usd: float` and `token_limit: int` thresholds with a `check_budget()` method that raises `BudgetExceededError` when a threshold is reached, allowing agents to self-limit automatically.

- **Cache warming:** Add a `warm(pairs: list[tuple[LLMRequest, LLMResponse]])` method to `CompletionCache` that pre-populates the cache from a known set of request/response pairs, useful for seeding from a golden dataset.

- **`SQLiteDeduplicationStore` connection lifecycle:** Add `close()`/`__enter__`/`__exit__` for deterministic file-handle release in long-running services and test harnesses.

- **`SQLiteDeduplicationStore` TTL-based expiry:** A `ttl_days: int | None` constructor parameter that records each hash's insertion timestamp and prunes rows older than N days, preventing unbounded database growth in continuous ingestion jobs.

- **Cross-process `RedisDeduplicationStore`:** For multi-worker deployments where multiple processes share one ingestion pipeline, a Redis-backed store with server-side TTL would provide shared dedup state without changing any consumer interface.

---

## Usage examples

### Budget tracking across a session

```python
from llm_agents.infra.cost_latency_optimization import BudgetTracker
from llm_agents.infra.inference_routing import LLMRequest, Router, RoutingPolicy, Candidate

tracker = BudgetTracker()
# assume router is configured with real or fake providers

for user_query in user_queries:
    request = LLMRequest("gpt-4o", [{"role": "user", "content": user_query}])
    response = await router.complete(request)
    tracker.track(response)

report = tracker.report()
print(f"Calls: {report.call_count}, Total tokens: {report.total_tokens}, "
      f"Cost: ${report.cost_usd:.6f}")
```

### Completion caching

```python
from llm_agents.infra.cost_latency_optimization import CompletionCache
from llm_agents.infra.inference_routing import LLMRequest

cache = CompletionCache(ttl_s=300.0, max_size=512)

request = LLMRequest(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is the capital of France?"}],
)
# First call: cache miss, goes to router
response1 = await cache.cached_complete(request, router)

# Second call: cache hit, returned immediately at zero cost
response2 = await cache.cached_complete(request, router)
assert response1 is response2  # same object from cache
```

### Concurrent batch dispatch

```python
from llm_agents.infra.cost_latency_optimization import Batcher
from llm_agents.infra.inference_routing import LLMRequest

batcher = Batcher(router)

requests = [
    LLMRequest("gpt-4o", [{"role": "user", "content": f"Summarize document {i}"}])
    for i in range(20)
]

results = await batcher.batch_complete(requests)

for i, result in enumerate(results):
    if isinstance(result, BaseException):
        print(f"Request {i} failed: {result}")
    else:
        print(f"Request {i}: {result.content[:80]}")
```
