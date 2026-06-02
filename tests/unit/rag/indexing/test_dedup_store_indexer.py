"""Integration tests for Indexer with pluggable DeduplicationStore.

Verifies:
- Default behaviour (no dedup_store) is unchanged from before
- dedup_store parameter is keyword-only
- InMemoryDeduplicationStore wired explicitly behaves identically to default
- SQLiteDeduplicationStore wired into Indexer persists across Indexer recreation
- reset_dedup() and seen_count delegate to the store
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.indexing import (
    Indexer,
    InMemoryDeduplicationStore,
    SQLiteDeduplicationStore,
)
from llm_agents.rag.vector_store import InMemoryVectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_indexer(
    dims: int = 4, **kwargs: object
) -> tuple[Indexer, FakeEmbedder, InMemoryVectorStore]:
    embedder = FakeEmbedder(dimensions=dims)
    store = InMemoryVectorStore()
    indexer = Indexer(embedder, store, **kwargs)
    return indexer, embedder, store


# ---------------------------------------------------------------------------
# S19: Default (no dedup_store) — duplicate chunk skipped, backward compat
# ---------------------------------------------------------------------------


class TestIndexerDefaultStore:
    def test_duplicate_chunk_skipped_default(self) -> None:
        indexer, embedder, vs = _make_indexer()
        indexer.index("d1", "hello world")
        assert indexer.seen_count == 1

        # Re-index same content — chunk must be skipped
        indexer.index("d1", "hello world")
        assert indexer.seen_count == 1
        assert embedder.embed_count == 1  # embedder called only once

    def test_seen_count_increments_on_new_chunk(self) -> None:
        indexer, _, _ = _make_indexer()
        indexer.index("d1", "chunk one")
        indexer.index("d2", "chunk two")
        assert indexer.seen_count == 2

    def test_reset_dedup_clears_seen_count(self) -> None:
        indexer, _, _ = _make_indexer()
        indexer.index("d1", "hello")
        assert indexer.seen_count == 1
        indexer.reset_dedup()
        assert indexer.seen_count == 0


# ---------------------------------------------------------------------------
# S20: dedup_store is keyword-only
# ---------------------------------------------------------------------------


class TestIndexerDeduplicateStoreKeywordOnly:
    def test_dedup_store_keyword_only(self) -> None:
        embedder = FakeEmbedder(dimensions=4)
        vs = InMemoryVectorStore()
        store = InMemoryDeduplicationStore()
        with pytest.raises(TypeError):
            # Passing store as 4th positional argument must raise TypeError
            Indexer(embedder, vs, None, store)  # type: ignore[call-overload]

    def test_dedup_store_accepted_as_keyword(self) -> None:
        embedder = FakeEmbedder(dimensions=4)
        vs = InMemoryVectorStore()
        store = InMemoryDeduplicationStore()
        indexer = Indexer(embedder, vs, dedup_store=store)
        assert indexer.seen_count == 0


# ---------------------------------------------------------------------------
# S21: reset_dedup delegates to the store
# ---------------------------------------------------------------------------


class TestIndexerResetDedup:
    def test_reset_delegates_to_explicit_store(self) -> None:
        store = InMemoryDeduplicationStore()
        embedder = FakeEmbedder(dimensions=4)
        vs = InMemoryVectorStore()
        indexer = Indexer(embedder, vs, dedup_store=store)
        indexer.index("d1", "hello")
        assert len(store) == 1
        indexer.reset_dedup()
        assert len(store) == 0
        assert indexer.seen_count == 0


# ---------------------------------------------------------------------------
# S23: SQLiteDeduplicationStore persists across Indexer recreation
# ---------------------------------------------------------------------------


class TestIndexerSQLitePersistence:
    def test_sqlite_store_persists_across_indexer_recreation(self, tmp_path: Path) -> None:
        db_path = tmp_path / "indexer.db"
        text = "Unique document text for dedup test"

        # First indexer: index the document
        store1 = SQLiteDeduplicationStore(db_path)
        embedder = FakeEmbedder(dimensions=4)
        vs = InMemoryVectorStore()
        idx1 = Indexer(embedder, vs, dedup_store=store1)
        report1 = idx1.index("d1", text)
        assert report1.chunks_added == 1
        assert report1.chunks_skipped == 0

        # Second indexer: same DB path, same text — chunk must be skipped
        store2 = SQLiteDeduplicationStore(db_path)
        embedder2 = FakeEmbedder(dimensions=4)
        vs2 = InMemoryVectorStore()
        idx2 = Indexer(embedder2, vs2, dedup_store=store2)
        report2 = idx2.index("d1", text)
        assert report2.chunks_skipped == 1
        assert report2.chunks_added == 0
        assert embedder2.embed_count == 0  # embedder not called for skipped chunk

    def test_sqlite_new_content_indexed_after_restart(self, tmp_path: Path) -> None:
        db_path = tmp_path / "indexer.db"

        # First indexer: index chunk A
        store1 = SQLiteDeduplicationStore(db_path)
        embedder = FakeEmbedder(dimensions=4)
        idx1 = Indexer(embedder, InMemoryVectorStore(), dedup_store=store1)
        idx1.index("d1", "chunk A")

        # Second indexer: index chunk B (new) — must be indexed, not skipped
        store2 = SQLiteDeduplicationStore(db_path)
        embedder2 = FakeEmbedder(dimensions=4)
        idx2 = Indexer(embedder2, InMemoryVectorStore(), dedup_store=store2)
        report2 = idx2.index("d2", "chunk B")
        assert report2.chunks_added == 1
        assert report2.chunks_skipped == 0


# ---------------------------------------------------------------------------
# S24: Indexer uses add_batch — hashes recorded atomically after all upserts
# ---------------------------------------------------------------------------


class TestIndexerAddBatch:
    def test_index_records_all_chunk_hashes_via_add_batch(self) -> None:
        """All chunk hashes for a document are recorded after indexing."""
        store = InMemoryDeduplicationStore()
        embedder = FakeEmbedder(dimensions=4)
        vs = InMemoryVectorStore()
        indexer = Indexer(embedder, vs, chunker=lambda t: t.split(), dedup_store=store)

        report = indexer.index("d1", "a b c")
        assert report.chunks_added == 3
        assert report.chunks_skipped == 0
        assert indexer.seen_count == 3

    def test_index_skips_all_chunks_on_second_call(self) -> None:
        """Re-indexing the same document skips every chunk (dedup via add_batch)."""
        store = InMemoryDeduplicationStore()
        embedder = FakeEmbedder(dimensions=4)
        vs = InMemoryVectorStore()
        indexer = Indexer(embedder, vs, chunker=lambda t: t.split(), dedup_store=store)

        indexer.index("d1", "a b c")
        assert embedder.embed_count == 1

        report2 = indexer.index("d1", "a b c")
        assert report2.chunks_skipped == 3
        assert report2.chunks_added == 0
        assert embedder.embed_count == 1  # embedder not called again

    def test_index_partial_update_only_re_embeds_changed_chunks(self) -> None:
        """When only some chunks change, only those are re-embedded."""
        store = InMemoryDeduplicationStore()
        embedder = FakeEmbedder(dimensions=4)
        vs = InMemoryVectorStore()
        indexer = Indexer(embedder, vs, chunker=lambda t: t.split(), dedup_store=store)

        indexer.index("d1", "a b c")  # 3 chunks indexed
        report2 = indexer.index("d1", "a b X")  # chunk "X" is new, "a" and "b" are seen
        assert report2.chunks_added == 1
        assert report2.chunks_skipped == 2


# ---------------------------------------------------------------------------
# Exports — importable from rag/indexing
# ---------------------------------------------------------------------------


class TestRagIndexingExports:
    def test_dedup_store_importable_from_rag_indexing(self) -> None:
        from llm_agents.rag.indexing import (  # noqa: PLC0415
            DeduplicationStore,
            InMemoryDeduplicationStore,
            SQLiteDeduplicationStore,
        )

        assert DeduplicationStore is not None
        assert InMemoryDeduplicationStore is not None
        assert SQLiteDeduplicationStore is not None
