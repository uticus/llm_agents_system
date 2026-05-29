# agent_memory

## Overview

The `agent_memory` module provides the memory subsystem for LLM agents. It models memory in two tiers that mirror how human working memory and long-term recall operate: a token-bounded short-term buffer for the active context window, and an append-only long-term store with keyword-plus-recency retrieval. The module exists so that agents can maintain conversational state within a token budget, persist observations across turns, and retrieve relevant past knowledge without loading the entire history into each prompt. It is designed as a self-contained component that other modules (planning, hierarchical agents, etc.) can inject without depending on a specific persistence backend.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `MemoryItem` | dataclass | Single unit of storage for both memory tiers. |
| `ShortTermMemory` | class | Token-bounded FIFO buffer for working memory. |
| `LongTermMemory` | class | Append-only in-memory store with retrieval methods. |
| `MemoryStore` | Protocol | Pluggable persistence interface for long-term backends. |
| `InMemoryStore` | class | Default `MemoryStore` implementation backed by a plain list. |

### `MemoryItem`

```
MemoryItem(
    content: str,
    role: str,
    timestamp: float,
    metadata: dict[str, Any] = {},
    token_count: int = 0,
)
```

`token_count` is auto-estimated as `ceil(len(content) / 4)` when left at `0`. The minimum stored value is `1` to prevent zero-cost items from causing infinite eviction loops.

### `ShortTermMemory`

```
ShortTermMemory(token_budget: int = 2048)
```

| Method | Signature | Description |
|---|---|---|
| `add` | `(item: MemoryItem) -> None` | Append item, evicting oldest items until the budget allows it. |
| `items` | `() -> list[MemoryItem]` | Return all buffered items in oldest-first order. |
| `total_tokens` | `() -> int` | Current total estimated token count. |
| `clear` | `() -> None` | Remove all items. |

### `LongTermMemory`

```
LongTermMemory()
```

| Method | Signature | Description |
|---|---|---|
| `add` | `(item: MemoryItem) -> None` | Append item to the store. |
| `recent` | `(n: int) -> list[MemoryItem]` | Return the n most recently added items. |
| `search` | `(query: str, limit: int = 10) -> list[MemoryItem]` | Return up to `limit` items ranked by keyword overlap and recency. |
| `clear` | `() -> None` | Remove all items. |

### `MemoryStore` (Protocol)

```
@runtime_checkable
class MemoryStore(Protocol):
    def save(self, item: MemoryItem) -> None: ...
    def load(self, limit: int = 100) -> list[MemoryItem]: ...
    def search(self, query: str, limit: int = 10) -> list[MemoryItem]: ...
    def clear(self) -> None: ...
```

Satisfies `isinstance(store, MemoryStore)` checks at runtime due to `@runtime_checkable`.

### `InMemoryStore`

```
InMemoryStore()
```

Satisfies `MemoryStore` via structural subtyping. Same interface: `save`, `load`, `search`, `clear`.

---

## Architecture

### Conceptual view

```
                          Agent runtime
                               |
              +----------------+----------------+
              |                                 |
    ShortTermMemory                    LongTermMemory / InMemoryStore
   (token-bounded deque)           (append-only list + keyword search)
              |                                 |
         MemoryItem                        MemoryItem
         (content, role,               (content, role,
          timestamp, metadata,          timestamp, metadata,
          token_count)                  token_count)
```

The two tiers share the same `MemoryItem` data model but have different eviction and retrieval semantics. `ShortTermMemory` is the fast path: every call to `add` is O(k) where k is the number of items evicted, which is bounded by the budget. `LongTermMemory` is the slow path: retrieval is O(n log n) over all stored items.

### Data flow

1. Agent receives a turn (user message, observation, tool output).
2. Agent constructs a `MemoryItem` with the appropriate `role` and `timestamp`.
3. The item is added to `ShortTermMemory.add()` — oldest items are evicted if the budget is exceeded.
4. The same item (or a distilled version) may also be written to `LongTermMemory.add()` for persistence.
5. Before calling the LLM, the agent calls `ShortTermMemory.items()` to build the messages list.
6. When relevant background knowledge is needed, the agent calls `LongTermMemory.search(query)` to retrieve ranked items and injects them as additional context.

### Key abstractions

**`MemoryItem`** — the universal unit of storage. It carries semantic role information (`"user"`, `"assistant"`, `"system"`, `"observation"`) alongside raw content, so callers can reconstruct a conversation transcript or filter by role. The built-in token estimation (`ceil(len / 4)`) makes the model usable without a real tokenizer.

**`ShortTermMemory`** — models the agent's context window. The token budget maps directly to the model's context limit. The FIFO eviction policy preserves the most recent context, which is the information most relevant to the current turn.

**`LongTermMemory` / `MemoryStore` / `InMemoryStore`** — models persistent episodic memory. The retrieval function combines keyword overlap (`matched_words / total_query_words`) with a recency weight (`0.1 / (rank + 1)`) so that recent items with even partial keyword matches can surface over older but more complete matches. The `MemoryStore` protocol decouples the retrieval logic from the backend: a production deployment can swap `InMemoryStore` for a vector database or SQL-backed implementation without any change to the calling code.

---

## Design decisions and tradeoffs

- **Decision**: Token budget enforced by character approximation (`ceil(len / 4)`). **Why**: Exact tokenization requires a model-specific tokenizer which is a heavyweight dependency. The approximation is sufficient for budget planning and avoids a hard coupling to any one model. **Tradeoff**: Actual token counts can deviate by 10-30% from model reality, particularly for code, non-ASCII text, or short tokens. Agents that are tight on context may overflow or under-fill the window.

- **Decision**: FIFO eviction on `ShortTermMemory`. **Why**: Simpler than importance-weighted eviction and keeps the most recent messages, which is the standard assumption for conversational agents. **Tradeoff**: Old but important system messages (e.g. instructions) can be evicted. Callers should add system messages last or use a separate protected slot.

- **Decision**: `MemoryStore` is a structural `Protocol` with `@runtime_checkable`. **Why**: Allows any class that happens to implement the right methods to satisfy the interface without inheritance, which reduces coupling and enables third-party backends. **Tradeoff**: The protocol only checks method presence at runtime, not signatures, so type errors in backend implementations are caught only by static analysis or at call time.

- **Decision**: Retrieval scoring combines keyword overlap and recency but has no vector similarity. **Why**: Zero additional dependencies; works offline and deterministically. **Tradeoff**: Recall quality is limited for paraphrase queries where the query words differ from the stored content words. A production system should replace or augment this with embedding-based retrieval.

- **Decision**: `LongTermMemory` stores items in insertion order with no eviction. **Why**: Keeps all information available for search and avoids data loss decisions at the storage layer. **Tradeoff**: Memory grows without bound. For long-running agents this becomes a performance problem.

---

## Scaling concerns

- `ShortTermMemory` is O(1) amortized for `add` when the buffer is at steady state. Under high-frequency event streams the eviction loop can become O(n) if many small items are replaced by one large item.
- `LongTermMemory.search` is O(n log n) over all stored items. At 10,000 items with average 50-word content, a single search takes approximately 5-20 ms on a modern CPU — acceptable for per-turn retrieval, but not for high-frequency batch pipelines.
- `InMemoryStore` holds all items in the Python process heap. For agents running for hours with frequent observations, memory footprint will grow proportionally to event volume. There is no built-in pruning.
- Thread safety is not guaranteed. Both `ShortTermMemory` and `LongTermMemory` use plain Python collections with no locking. Concurrent writes from multiple coroutines require external synchronization.

---

## Future improvements

- **Embedding-based retrieval**: Replace or augment the keyword scorer in `_search` with cosine similarity over dense embeddings. This would improve recall for paraphrase queries and is the standard production approach.
- **Eviction policies for `LongTermMemory`**: Add TTL-based or importance-weighted eviction to bound memory growth. Importance could be estimated from access frequency or explicit caller-supplied scores on `MemoryItem`.
- **Protected slots in `ShortTermMemory`**: Allow callers to mark certain items (e.g. system instructions) as non-evictable so they survive budget pressure.
- **Async-safe collections**: Wrap the internal `deque` and `list` with `asyncio.Lock` or replace them with thread-safe structures to support concurrent agent coroutines sharing a memory instance.
- **Pluggable backend wiring**: Provide a factory or dependency-injection helper that selects `InMemoryStore` vs. a database-backed store based on configuration, so production deployments require no code changes.

---

## Usage examples

**Short-term buffer for a conversational agent:**

```python
import time
from llm_agents.core.agent_memory import MemoryItem, ShortTermMemory

stm = ShortTermMemory(token_budget=2048)

stm.add(MemoryItem(content="You are a helpful assistant.", role="system", timestamp=time.monotonic()))
stm.add(MemoryItem(content="What is the capital of France?", role="user", timestamp=time.monotonic()))
stm.add(MemoryItem(content="The capital of France is Paris.", role="assistant", timestamp=time.monotonic()))

# Build messages list for the next LLM call
messages = [{"role": item.role, "content": item.content} for item in stm.items()]
```

**Long-term memory with keyword search:**

```python
import time
from llm_agents.core.agent_memory import MemoryItem, LongTermMemory

ltm = LongTermMemory()

ltm.add(MemoryItem(content="User prefers concise answers.", role="observation", timestamp=time.monotonic()))
ltm.add(MemoryItem(content="Project deadline is end of Q3.", role="observation", timestamp=time.monotonic()))
ltm.add(MemoryItem(content="The API key is stored in .env.", role="observation", timestamp=time.monotonic()))

hits = ltm.search("deadline project", limit=5)
for item in hits:
    print(item.content)
```

**Custom persistence backend:**

```python
from llm_agents.core.agent_memory import MemoryItem, MemoryStore

class RedisMemoryStore:
    """Example structural implementation of MemoryStore backed by Redis."""

    def save(self, item: MemoryItem) -> None:
        # serialize and push to Redis list
        ...

    def load(self, limit: int = 100) -> list[MemoryItem]:
        # pop last `limit` items from Redis list
        ...

    def search(self, query: str, limit: int = 10) -> list[MemoryItem]:
        # full-text or embedding search
        ...

    def clear(self) -> None:
        # delete Redis key
        ...

# Verify structural conformance at test time
assert isinstance(RedisMemoryStore(), MemoryStore)
```
