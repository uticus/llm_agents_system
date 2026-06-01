"""Content-hash deduplication store interface and implementations.

The :class:`DeduplicationStore` protocol defines a minimal set/persist abstraction
for tracking previously seen content hashes.  The two built-in implementations are:

* :class:`InMemoryDeduplicationStore` — backed by a plain :class:`set`; resets on
  process restart (same behaviour as the ``_seen_hashes`` sets previously embedded
  directly in :class:`~llm_agents.data.ingestion.IngestionPipeline` and
  :class:`~llm_agents.rag.indexing.Indexer`).

* :class:`SQLiteDeduplicationStore` — backed by a SQLite database file (stdlib
  ``sqlite3``); hashes survive process restarts, allowing incremental ingestion/indexing
  across multiple runs.

No external dependencies are required for either implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class DeduplicationStore(Protocol):
    """Protocol for content-hash deduplication stores.

    Any object that implements ``add``, ``__contains__``, ``reset``, and ``__len__``
    satisfies this protocol (structural subtyping — no inheritance required).
    """

    def add(self, hash: str) -> None:
        """Record *hash* as seen.  Idempotent: calling with an existing hash is a no-op."""
        ...

    def __contains__(self, hash: str) -> bool:
        """Return ``True`` if *hash* has been added since the last :meth:`reset`."""
        ...

    def reset(self) -> None:
        """Clear all stored hashes.  After this call ``len(self) == 0``."""
        ...

    def __len__(self) -> int:
        """Return the number of distinct hashes currently stored."""
        ...


class InMemoryDeduplicationStore:
    """In-memory deduplication store backed by a :class:`set`.

    This is the default store used by :class:`~llm_agents.data.ingestion.IngestionPipeline`
    and :class:`~llm_agents.rag.indexing.Indexer` when no explicit store is provided.
    Its behaviour is identical to the ``_seen_hashes: set[str]`` that was previously
    embedded in those classes.

    State is lost when the process exits.
    """

    def __init__(self) -> None:
        self._hashes: set[str] = set()

    def add(self, hash: str) -> None:
        """Record *hash* as seen."""
        self._hashes.add(hash)

    def __contains__(self, hash: str) -> bool:  # type: ignore[override]
        """Return ``True`` if *hash* has been added since the last :meth:`reset`."""
        return hash in self._hashes

    def reset(self) -> None:
        """Clear all stored hashes."""
        self._hashes.clear()

    def __len__(self) -> int:
        """Return the number of distinct hashes currently stored."""
        return len(self._hashes)


class SQLiteDeduplicationStore:
    """Durable deduplication store backed by a SQLite database file.

    Hashes are written to a single-column table and committed immediately on each
    :meth:`add` call, so they survive process restarts.  A new instance pointing to
    the same file will recognise all hashes written by previous instances.

    Args:
        path: Path to the SQLite database file.  The file (and any missing parent
              directories that already exist) is created automatically if it does not
              exist.  Pass ``":memory:"`` for an in-memory SQLite database (useful in
              tests that do not need persistence).

    Raises:
        sqlite3.OperationalError: If *path* refers to a directory that does not exist.
    """

    def __init__(self, path: str | Path) -> None:
        import sqlite3  # deferred — keeps module importable without touching sqlite3

        self._conn = sqlite3.connect(str(path))
        self._conn.execute("CREATE TABLE IF NOT EXISTS hashes (hash TEXT PRIMARY KEY)")
        self._conn.commit()

    def add(self, hash: str) -> None:
        """Record *hash* as seen.  Commits immediately.  Idempotent."""
        self._conn.execute("INSERT OR IGNORE INTO hashes VALUES (?)", (hash,))
        self._conn.commit()

    def __contains__(self, hash: str) -> bool:  # type: ignore[override]
        """Return ``True`` if *hash* is present in the store."""
        row = self._conn.execute("SELECT 1 FROM hashes WHERE hash = ?", (hash,)).fetchone()
        return row is not None

    def reset(self) -> None:
        """Delete all hashes from the store and commit."""
        self._conn.execute("DELETE FROM hashes")
        self._conn.commit()

    def __len__(self) -> int:
        """Return the number of distinct hashes currently stored."""
        row = self._conn.execute("SELECT COUNT(*) FROM hashes").fetchone()
        return int(row[0])
