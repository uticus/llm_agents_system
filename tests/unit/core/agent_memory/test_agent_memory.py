"""Unit tests for core/agent_memory.

Covers T1–T10 as specified in task-005 §test-criteria.
"""

from __future__ import annotations

import math
import time

from llm_agents.core.agent_memory import (
    InMemoryStore,
    LongTermMemory,
    MemoryItem,
    MemoryStore,
    ShortTermMemory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item(content: str, role: str = "user", token_count: int = 0) -> MemoryItem:
    return MemoryItem(
        content=content,
        role=role,
        timestamp=time.monotonic(),
        token_count=token_count,
    )


# ---------------------------------------------------------------------------
# T1 — MemoryItem token_count estimation
# ---------------------------------------------------------------------------


def test_memory_item_token_count_estimated_from_content():
    """T1a: token_count=0 triggers automatic estimation."""
    item = _item("Hello world")
    expected = math.ceil(len("Hello world") / 4)
    assert item.token_count == expected


def test_memory_item_explicit_token_count_not_overridden():
    """T1b: Explicit positive token_count is preserved."""
    item = _item("Hello world", token_count=42)
    assert item.token_count == 42


def test_memory_item_empty_content_has_min_token_count():
    """T1c: Empty content gets token_count of 1 (minimum)."""
    item = _item("")
    assert item.token_count == 1


# ---------------------------------------------------------------------------
# T2 — ShortTermMemory add and total_tokens
# ---------------------------------------------------------------------------


def test_short_term_memory_add_and_total_tokens():
    """T2: items() ordered oldest→newest; total_tokens is correct."""
    stm = ShortTermMemory(token_budget=1000)
    i1 = _item("First")
    i2 = _item("Second")
    stm.add(i1)
    stm.add(i2)
    assert stm.items() == [i1, i2]
    assert stm.total_tokens() == i1.token_count + i2.token_count


# ---------------------------------------------------------------------------
# T3 — ShortTermMemory trimming
# ---------------------------------------------------------------------------


def test_short_term_memory_trims_oldest():
    """T3: Adding items beyond budget drops oldest first."""
    # Each item gets token_count = ceil(len(content)/4)
    # "AAAA" → ceil(4/4) = 1; budget of 2 holds exactly 2 such items
    stm = ShortTermMemory(token_budget=2)
    i1 = _item("AAAA", token_count=1)
    i2 = _item("BBBB", token_count=1)
    i3 = _item("CCCC", token_count=1)
    stm.add(i1)
    stm.add(i2)
    stm.add(i3)  # should evict i1

    items = stm.items()
    assert i1 not in items
    assert i2 in items
    assert i3 in items
    assert stm.total_tokens() <= 2


def test_short_term_memory_multiple_trim_rounds():
    """T3b: A large item evicts multiple smaller items."""
    stm = ShortTermMemory(token_budget=10)
    for _ in range(5):
        stm.add(_item("AB", token_count=2))
    assert stm.total_tokens() == 10

    big = _item("X" * 80, token_count=10)  # needs 10 tokens
    stm.add(big)
    assert stm.total_tokens() <= 10
    assert stm.items()[-1] is big


# ---------------------------------------------------------------------------
# T4 — ShortTermMemory: single item larger than budget accepted
# ---------------------------------------------------------------------------


def test_short_term_memory_oversized_item_accepted():
    """T4: Single item larger than budget is accepted as sole item."""
    stm = ShortTermMemory(token_budget=5)
    small = _item("AB", token_count=2)
    stm.add(small)
    huge = _item("X" * 400, token_count=100)  # much bigger than budget
    stm.add(huge)
    assert stm.items() == [huge]
    assert stm.total_tokens() == 100  # exceeds budget but acceptable


# ---------------------------------------------------------------------------
# T5 — ShortTermMemory clear
# ---------------------------------------------------------------------------


def test_short_term_memory_clear():
    """T5: clear() removes all items and resets token count."""
    stm = ShortTermMemory(token_budget=1000)
    stm.add(_item("hello"))
    stm.clear()
    assert stm.items() == []
    assert stm.total_tokens() == 0


# ---------------------------------------------------------------------------
# T6 — LongTermMemory recent
# ---------------------------------------------------------------------------


def test_long_term_memory_recent_n():
    """T6: recent(n) returns n most recently added items."""
    ltm = LongTermMemory()
    items = [_item(f"item {i}") for i in range(5)]
    for it in items:
        ltm.add(it)
    recent = ltm.recent(3)
    assert recent == items[-3:]


def test_long_term_memory_recent_zero():
    """T6b: recent(0) returns []."""
    ltm = LongTermMemory()
    ltm.add(_item("x"))
    assert ltm.recent(0) == []


def test_long_term_memory_recent_more_than_stored():
    """T6c: recent(100) on a store with 2 items returns 2 items."""
    ltm = LongTermMemory()
    i1 = _item("a")
    i2 = _item("b")
    ltm.add(i1)
    ltm.add(i2)
    assert ltm.recent(100) == [i1, i2]


# ---------------------------------------------------------------------------
# T7 — LongTermMemory search
# ---------------------------------------------------------------------------


def test_long_term_memory_search_keyword_match():
    """T7a: Items containing query keywords are returned."""
    ltm = LongTermMemory()
    ltm.add(_item("The quick brown fox"))
    ltm.add(_item("Pack my box with five dozen liquor jugs"))
    ltm.add(_item("Hello world"))

    results = ltm.search("quick fox")
    assert len(results) >= 1
    assert any("quick" in r.content for r in results)


def test_long_term_memory_search_empty_query():
    """T7b: Empty query always returns []."""
    ltm = LongTermMemory()
    ltm.add(_item("anything"))
    assert ltm.search("") == []
    assert ltm.search("   ") == []


def test_long_term_memory_search_limit():
    """T7c: search respects limit parameter."""
    ltm = LongTermMemory()
    for i in range(10):
        ltm.add(_item(f"keyword item {i}"))
    results = ltm.search("keyword", limit=3)
    assert len(results) <= 3


def test_long_term_memory_search_no_match():
    """T7d: Query with no matching items returns []."""
    ltm = LongTermMemory()
    ltm.add(_item("completely unrelated"))
    results = ltm.search("zzz_unique_nonword")
    assert results == []


# ---------------------------------------------------------------------------
# T8 — LongTermMemory clear
# ---------------------------------------------------------------------------


def test_long_term_memory_clear():
    """T8: clear() removes all items."""
    ltm = LongTermMemory()
    ltm.add(_item("hello"))
    ltm.clear()
    assert ltm.recent(10) == []
    assert ltm.search("hello") == []


# ---------------------------------------------------------------------------
# T9 — InMemoryStore save + load
# ---------------------------------------------------------------------------


def test_in_memory_store_save_and_load():
    """T9a: save() then load() round-trips items; load respects limit."""
    store = InMemoryStore()
    items = [_item(f"item {i}") for i in range(5)]
    for it in items:
        store.save(it)
    loaded = store.load(limit=3)
    assert len(loaded) == 3
    assert loaded == items[-3:]


def test_in_memory_store_load_all():
    """T9b: load() without restriction returns all saved items."""
    store = InMemoryStore()
    items = [_item(f"x {i}") for i in range(3)]
    for it in items:
        store.save(it)
    assert store.load(limit=100) == items


def test_in_memory_store_search():
    """T9c: search() returns matching items."""
    store = InMemoryStore()
    store.save(_item("Python programming language"))
    store.save(_item("Machine learning and AI"))
    store.save(_item("Database optimization"))
    results = store.search("Python programming", limit=5)
    assert any("Python" in r.content for r in results)


# ---------------------------------------------------------------------------
# T10 — InMemoryStore satisfies MemoryStore protocol
# ---------------------------------------------------------------------------


def test_in_memory_store_satisfies_protocol():
    """T10: isinstance(InMemoryStore(), MemoryStore) is True (runtime_checkable)."""
    store = InMemoryStore()
    assert isinstance(store, MemoryStore)


def test_long_term_memory_not_memorystore():
    """T10b: LongTermMemory does NOT satisfy MemoryStore (missing save/load names)."""
    ltm = LongTermMemory()
    # LongTermMemory has .add() not .save()/.load() — should NOT satisfy the protocol
    assert not isinstance(ltm, MemoryStore)
