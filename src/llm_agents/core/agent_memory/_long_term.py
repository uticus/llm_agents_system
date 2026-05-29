"""Long-term memory store with recency + keyword retrieval.

Provides three classes:

- :class:`LongTermMemory` — in-memory store with retrieval methods.
- :class:`MemoryStore` — :class:`typing.Protocol` for pluggable persistence backends.
- :class:`InMemoryStore` — default implementation satisfying :class:`MemoryStore`
  via structural subtyping (no inheritance required).

Retrieval scoring
-----------------
For a non-empty query, each item receives a score::

    score = overlap_fraction + recency_weight

where ``overlap_fraction = matched_words / total_query_words`` and
``recency_weight = 0.1 / (rank + 1)`` with rank 0 being the most recent item.
Items with score 0 are excluded.  Results are sorted descending by score and
truncated to ``limit``.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from llm_agents.core.agent_memory._models import MemoryItem


def _words(text: str) -> set[str]:
    """Return lowercase word set for *text*."""
    return set(re.findall(r"\w+", text.lower()))


def _score(item: MemoryItem, query_words: set[str], rank: int) -> float:
    """Compute relevance score for *item* given *query_words* and recency *rank*."""
    if not query_words:
        return 0.0
    overlap = len(query_words & _words(item.content))
    if overlap == 0:
        return 0.0
    overlap_fraction = overlap / len(query_words)
    recency_weight = 0.1 / (rank + 1)
    return overlap_fraction + recency_weight


def _search(items: list[MemoryItem], query: str, limit: int) -> list[MemoryItem]:
    """Shared search logic for :class:`LongTermMemory` and :class:`InMemoryStore`."""
    q_words = _words(query)
    if not q_words:
        return []
    # Rank by timestamp descending (most recent = rank 0)
    sorted_items = sorted(items, key=lambda it: it.timestamp, reverse=True)
    scored = [
        (item, _score(item, q_words, rank))
        for rank, item in enumerate(sorted_items)
    ]
    filtered = sorted(
        ((item, s) for item, s in scored if s > 0),
        key=lambda x: x[1],
        reverse=True,
    )
    return [item for item, _ in filtered[:limit]]


class LongTermMemory:
    """Append-only in-memory long-term memory with retrieval.

    All items are kept in insertion order.  Retrieval methods do not mutate
    the store.
    """

    def __init__(self) -> None:
        self._items: list[MemoryItem] = []

    def add(self, item: MemoryItem) -> None:
        """Append *item* to the store."""
        self._items.append(item)

    def recent(self, n: int) -> list[MemoryItem]:
        """Return the *n* most recently added items (latest last).

        Returns an empty list if ``n <= 0`` or the store is empty.
        """
        if n <= 0:
            return []
        return list(self._items[-n:])

    def search(self, query: str, limit: int = 10) -> list[MemoryItem]:
        """Return up to *limit* items ranked by keyword overlap + recency.

        An empty *query* always returns an empty list.
        """
        return _search(self._items, query, limit)

    def clear(self) -> None:
        """Remove all items from the store."""
        self._items.clear()


@runtime_checkable
class MemoryStore(Protocol):
    """Persistence protocol for long-term memory backends.

    Implementors conform structurally — no need to inherit from this class.
    Annotate with ``@runtime_checkable`` so ``isinstance(store, MemoryStore)``
    works in tests.
    """

    def save(self, item: MemoryItem) -> None:
        """Persist *item* to the backend."""
        ...

    def load(self, limit: int = 100) -> list[MemoryItem]:
        """Return up to *limit* most recently saved items."""
        ...

    def search(self, query: str, limit: int = 10) -> list[MemoryItem]:
        """Return up to *limit* items ranked by relevance to *query*."""
        ...

    def clear(self) -> None:
        """Delete all stored items."""
        ...


class InMemoryStore:
    """Default :class:`MemoryStore` implementation backed by a plain list.

    Satisfies the :class:`MemoryStore` protocol via structural subtyping —
    does not inherit from it.
    """

    def __init__(self) -> None:
        self._items: list[MemoryItem] = []

    def save(self, item: MemoryItem) -> None:
        """Append *item* to the in-memory list."""
        self._items.append(item)

    def load(self, limit: int = 100) -> list[MemoryItem]:
        """Return up to *limit* most recently saved items (latest last)."""
        if limit <= 0:
            return []
        return list(self._items[-limit:])

    def search(self, query: str, limit: int = 10) -> list[MemoryItem]:
        """Return up to *limit* items ranked by keyword overlap + recency."""
        return _search(self._items, query, limit)

    def clear(self) -> None:
        """Remove all items."""
        self._items.clear()
