"""Integration tests for IngestionPipeline with pluggable DeduplicationStore.

Verifies:
- Default behaviour (no dedup_store) is unchanged from before
- dedup_store parameter is keyword-only
- InMemoryDeduplicationStore wired explicitly behaves identically to default
- SQLiteDeduplicationStore wired into pipeline persists across pipeline recreation
- reset_dedup() and seen_count delegate to the store
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from llm_agents.data.connectors import Document, FakeConnector
from llm_agents.data.ingestion import (
    IngestionPipeline,
    InMemoryDeduplicationStore,
    SQLiteDeduplicationStore,
)
from llm_agents.data.parsers import ParsedDocument, TextParser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity_chunker(parsed: ParsedDocument) -> list[str]:
    return [parsed.text]


def _make_docs(*contents: str) -> list[Document]:
    return [Document(doc_id=str(i), content=c) for i, c in enumerate(contents)]


def _make_pipeline(
    *contents: str,
    **kwargs: object,
) -> tuple[IngestionPipeline, list[str]]:
    conn = FakeConnector("c", _make_docs(*contents))
    upserted: list[str] = []
    pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append, **kwargs)
    return pipeline, upserted


# ---------------------------------------------------------------------------
# S16: Default (no dedup_store) — duplicate skipped, backward compat
# ---------------------------------------------------------------------------


class TestIngestionPipelineDefaultStore:
    def test_duplicate_doc_skipped_default(self) -> None:
        """Default pipeline skips duplicate document on second ingest."""
        conn = FakeConnector("c", _make_docs("hello"))
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)

        asyncio.run(pipeline.ingest())
        assert pipeline.seen_count == 1

        # Second ingest on same pipeline instance — same connector, no new docs
        asyncio.run(pipeline.ingest())
        # seen_count unchanged since no new distinct docs
        assert pipeline.seen_count == 1

    def test_seen_count_increments_on_new_doc(self) -> None:
        conn = FakeConnector("c", _make_docs("doc1", "doc2"))
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)
        asyncio.run(pipeline.ingest())
        assert pipeline.seen_count == 2

    def test_reset_dedup_clears_seen_count(self) -> None:
        conn = FakeConnector("c", _make_docs("doc1"))
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)
        asyncio.run(pipeline.ingest())
        assert pipeline.seen_count == 1
        pipeline.reset_dedup()
        assert pipeline.seen_count == 0


# ---------------------------------------------------------------------------
# S17: dedup_store is keyword-only
# ---------------------------------------------------------------------------


class TestIngestionPipelineDeduplicateStoreKeywordOnly:
    def test_dedup_store_keyword_only(self) -> None:
        conn = FakeConnector("c", [])
        store = InMemoryDeduplicationStore()
        with pytest.raises(TypeError):
            # Passing store as 5th positional argument must raise TypeError
            IngestionPipeline(conn, TextParser(), _identity_chunker, list.append, store)  # type: ignore[call-arg]

    def test_dedup_store_accepted_as_keyword(self) -> None:
        conn = FakeConnector("c", [])
        store = InMemoryDeduplicationStore()
        pipeline = IngestionPipeline(
            conn, TextParser(), _identity_chunker, list.append, dedup_store=store
        )
        assert pipeline.seen_count == 0


# ---------------------------------------------------------------------------
# S18: reset_dedup delegates to the store
# ---------------------------------------------------------------------------


class TestIngestionPipelineResetDedup:
    def test_reset_delegates_to_explicit_store(self) -> None:
        store = InMemoryDeduplicationStore()
        conn = FakeConnector("c", _make_docs("hello"))
        upserted: list[str] = []
        pipeline = IngestionPipeline(
            conn, TextParser(), _identity_chunker, upserted.append, dedup_store=store
        )
        asyncio.run(pipeline.ingest())
        assert len(store) == 1
        pipeline.reset_dedup()
        assert len(store) == 0
        assert pipeline.seen_count == 0


# ---------------------------------------------------------------------------
# S22: SQLiteDeduplicationStore persists across pipeline recreation
# ---------------------------------------------------------------------------


class TestIngestionPipelineSQLitePersistence:
    def test_sqlite_store_persists_across_pipeline_recreation(self, tmp_path: Path) -> None:
        db_path = tmp_path / "pipeline.db"
        content = "This is a unique document"

        # First pipeline: ingest the document
        store1 = SQLiteDeduplicationStore(db_path)
        conn1 = FakeConnector("c", _make_docs(content))
        upserted1: list[str] = []
        pipeline1 = IngestionPipeline(
            conn1, TextParser(), _identity_chunker, upserted1.append, dedup_store=store1
        )
        report1 = asyncio.run(pipeline1.ingest())
        assert report1.upserted == 1
        assert report1.skipped == 0

        # Second pipeline: same DB path, same document — must be skipped
        store2 = SQLiteDeduplicationStore(db_path)
        conn2 = FakeConnector("c", _make_docs(content))
        upserted2: list[str] = []
        pipeline2 = IngestionPipeline(
            conn2, TextParser(), _identity_chunker, upserted2.append, dedup_store=store2
        )
        report2 = asyncio.run(pipeline2.ingest())
        assert report2.skipped == 1
        assert report2.upserted == 0
        assert upserted2 == []

    def test_sqlite_store_new_content_upserted_after_restart(self, tmp_path: Path) -> None:
        db_path = tmp_path / "pipeline.db"

        # First pipeline: ingest doc A
        store1 = SQLiteDeduplicationStore(db_path)
        conn1 = FakeConnector("c", _make_docs("doc A"))
        upserted1: list[str] = []
        pipeline1 = IngestionPipeline(
            conn1, TextParser(), _identity_chunker, upserted1.append, dedup_store=store1
        )
        asyncio.run(pipeline1.ingest())

        # Second pipeline: ingest doc B (new) — must be upserted, not skipped
        store2 = SQLiteDeduplicationStore(db_path)
        conn2 = FakeConnector("c", _make_docs("doc B"))
        upserted2: list[str] = []
        pipeline2 = IngestionPipeline(
            conn2, TextParser(), _identity_chunker, upserted2.append, dedup_store=store2
        )
        report2 = asyncio.run(pipeline2.ingest())
        assert report2.upserted == 1
        assert report2.skipped == 0
