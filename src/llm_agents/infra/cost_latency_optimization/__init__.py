"""Cost/latency optimization subsystem: caching, batching, budget tracking, and dedup.

Public surface
--------------
Budget tracking::

    from llm_agents.infra.cost_latency_optimization import BudgetTracker, BudgetReport

    tracker = BudgetTracker()
    tracker.track(response)
    report = tracker.report()

Completion cache::

    from llm_agents.infra.cost_latency_optimization import CompletionCache

    cache = CompletionCache(ttl_s=60.0, max_size=128)
    response = await cache.cached_complete(request, router)

Request batcher::

    from llm_agents.infra.cost_latency_optimization import Batcher

    batcher = Batcher(router)
    results = await batcher.batch_complete([req1, req2, req3])

Deduplication store::

    from llm_agents.infra.cost_latency_optimization import (
        DeduplicationStore,
        InMemoryDeduplicationStore,
        SQLiteDeduplicationStore,
    )

    # In-memory (default — lost on restart):
    store = InMemoryDeduplicationStore()

    # Durable (survives restarts):
    store = SQLiteDeduplicationStore("dedup.db")

    store.add("abc123")
    "abc123" in store  # True
    store.reset()
"""

from llm_agents.infra.cost_latency_optimization._batcher import Batcher
from llm_agents.infra.cost_latency_optimization._budget import BudgetReport, BudgetTracker
from llm_agents.infra.cost_latency_optimization._cache import CompletionCache
from llm_agents.infra.cost_latency_optimization._dedup import (
    DeduplicationStore,
    InMemoryDeduplicationStore,
    SQLiteDeduplicationStore,
)

__all__ = [
    "Batcher",
    "BudgetReport",
    "BudgetTracker",
    "CompletionCache",
    "DeduplicationStore",
    "InMemoryDeduplicationStore",
    "SQLiteDeduplicationStore",
]
