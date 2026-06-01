"""Unit tests for DeduplicationStore implementations.

Covers:
- InMemoryDeduplicationStore: init empty, add/contains, reset, len, case-sensitivity
- SQLiteDeduplicationStore: same functional tests (using ":memory:"), plus
  persistence across instance recreation (using tmp_path)
- DeduplicationStore Protocol: runtime_checkable isinstance
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from llm_agents.infra.cost_latency_optimization import (
    DeduplicationStore,
    InMemoryDeduplicationStore,
    SQLiteDeduplicationStore,
)

# ---------------------------------------------------------------------------
# T1: InMemoryDeduplicationStore
# ---------------------------------------------------------------------------


class TestInMemoryDeduplicationStore:
    def test_initially_empty(self) -> None:
        store = InMemoryDeduplicationStore()
        assert len(store) == 0
        assert "abc" not in store

    def test_add_then_contains(self) -> None:
        store = InMemoryDeduplicationStore()
        store.add("abc")
        assert "abc" in store
        assert len(store) == 1

    def test_duplicate_add_does_not_increment_len(self) -> None:
        store = InMemoryDeduplicationStore()
        store.add("abc")
        store.add("abc")
        assert len(store) == 1

    def test_reset_clears_all_hashes(self) -> None:
        store = InMemoryDeduplicationStore()
        store.add("abc")
        store.add("def")
        store.reset()
        assert len(store) == 0
        assert "abc" not in store
        assert "def" not in store

    def test_case_sensitive(self) -> None:
        store = InMemoryDeduplicationStore()
        store.add("ABC")
        assert "abc" not in store
        assert "ABC" in store

    def test_multiple_distinct_hashes(self) -> None:
        store = InMemoryDeduplicationStore()
        store.add("h1")
        store.add("h2")
        store.add("h3")
        assert len(store) == 3
        assert "h1" in store
        assert "h2" in store
        assert "h3" in store

    def test_missing_hash_returns_false(self) -> None:
        store = InMemoryDeduplicationStore()
        store.add("h1")
        assert "h2" not in store

    def test_reset_then_readd(self) -> None:
        store = InMemoryDeduplicationStore()
        store.add("abc")
        store.reset()
        store.add("abc")
        assert len(store) == 1
        assert "abc" in store


# ---------------------------------------------------------------------------
# T2: SQLiteDeduplicationStore — functional (in-memory DB)
# ---------------------------------------------------------------------------


class TestSQLiteDeduplicationStoreInMemory:
    def _store(self) -> SQLiteDeduplicationStore:
        return SQLiteDeduplicationStore(":memory:")

    def test_initially_empty(self) -> None:
        store = self._store()
        assert len(store) == 0
        assert "abc" not in store

    def test_add_then_contains(self) -> None:
        store = self._store()
        store.add("abc")
        assert "abc" in store
        assert len(store) == 1

    def test_duplicate_add_idempotent(self) -> None:
        store = self._store()
        store.add("abc")
        store.add("abc")  # must not raise; idempotent
        assert len(store) == 1

    def test_reset_clears_all_hashes(self) -> None:
        store = self._store()
        store.add("abc")
        store.reset()
        assert len(store) == 0
        assert "abc" not in store

    def test_multiple_distinct_hashes(self) -> None:
        store = self._store()
        store.add("h1")
        store.add("h2")
        store.add("h3")
        assert len(store) == 3
        assert "h1" in store
        assert "h2" in store
        assert "h3" in store

    def test_missing_hash_returns_false(self) -> None:
        store = self._store()
        store.add("h1")
        assert "h2" not in store

    def test_case_sensitive(self) -> None:
        store = self._store()
        store.add("ABC")
        assert "abc" not in store

    def test_reset_then_readd(self) -> None:
        store = self._store()
        store.add("abc")
        store.reset()
        store.add("abc")
        assert len(store) == 1
        assert "abc" in store


# ---------------------------------------------------------------------------
# T3: SQLiteDeduplicationStore — persistence (file DB)
# ---------------------------------------------------------------------------


class TestSQLiteDeduplicationStorePersistence:
    def test_db_file_created_on_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "dedup.db"
        assert not path.exists()
        SQLiteDeduplicationStore(path)
        assert path.exists()

    def test_persistence_across_instance_recreation(self, tmp_path: Path) -> None:
        path = tmp_path / "dedup.db"
        s1 = SQLiteDeduplicationStore(path)
        s1.add("abc")
        del s1

        s2 = SQLiteDeduplicationStore(path)
        assert "abc" in s2
        assert len(s2) == 1

    def test_multiple_hashes_persist(self, tmp_path: Path) -> None:
        path = tmp_path / "dedup.db"
        s1 = SQLiteDeduplicationStore(path)
        s1.add("h1")
        s1.add("h2")
        s1.add("h3")
        del s1

        s2 = SQLiteDeduplicationStore(path)
        assert len(s2) == 3
        assert "h1" in s2
        assert "h2" in s2
        assert "h3" in s2

    def test_reset_persists_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "dedup.db"
        s1 = SQLiteDeduplicationStore(path)
        s1.add("abc")
        s1.reset()
        del s1

        s2 = SQLiteDeduplicationStore(path)
        assert "abc" not in s2
        assert len(s2) == 0

    def test_second_instance_does_not_fail_on_existing_table(self, tmp_path: Path) -> None:
        # CREATE TABLE IF NOT EXISTS must be idempotent
        path = tmp_path / "dedup.db"
        SQLiteDeduplicationStore(path)
        SQLiteDeduplicationStore(path)  # must not raise


# ---------------------------------------------------------------------------
# T4: Error handling
# ---------------------------------------------------------------------------


class TestSQLiteDeduplicationStoreErrors:
    def test_bad_directory_raises_operational_error(self) -> None:
        bad_path = Path("/nonexistent_dir_that_does_not_exist_xyz/dedup.db")
        with pytest.raises(sqlite3.OperationalError):
            SQLiteDeduplicationStore(bad_path)


# ---------------------------------------------------------------------------
# T5: Protocol — runtime_checkable isinstance
# ---------------------------------------------------------------------------


class TestDeduplicationStoreProtocol:
    def test_in_memory_satisfies_protocol(self) -> None:
        store = InMemoryDeduplicationStore()
        assert isinstance(store, DeduplicationStore)

    def test_sqlite_satisfies_protocol(self) -> None:
        store = SQLiteDeduplicationStore(":memory:")
        assert isinstance(store, DeduplicationStore)

    def test_plain_object_does_not_satisfy_protocol(self) -> None:
        assert not isinstance(object(), DeduplicationStore)
