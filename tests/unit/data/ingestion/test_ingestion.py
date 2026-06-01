"""Unit tests for data/ingestion: IngestionPipeline, IngestionReport."""

from __future__ import annotations

import asyncio
import hashlib

from llm_agents.data.connectors import Document, FakeConnector
from llm_agents.data.ingestion import IngestionPipeline, IngestionReport
from llm_agents.data.parsers import ParsedDocument, TextParser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity_chunker(parsed: ParsedDocument) -> list[str]:
    """Return the whole text as a single chunk."""
    return [parsed.text]


def _empty_chunker(parsed: ParsedDocument) -> list[str]:
    """Return no chunks (skip document)."""
    return []


def _split_chunker(parsed: ParsedDocument) -> list[str]:
    """Split on newlines, one chunk per non-empty line."""
    return [line for line in parsed.text.splitlines() if line.strip()]


def _make_docs(*contents: str) -> list[Document]:
    return [Document(doc_id=str(i), content=c) for i, c in enumerate(contents)]


def _md5(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


# ---------------------------------------------------------------------------
# IngestionReport
# ---------------------------------------------------------------------------


class TestIngestionReport:
    def test_defaults(self) -> None:
        report = IngestionReport()
        assert report.fetched == 0
        assert report.parsed == 0
        assert report.skipped == 0
        assert report.upserted == 0
        assert report.errors == []

    def test_full_construction(self) -> None:
        report = IngestionReport(fetched=10, parsed=8, skipped=2, upserted=15)
        assert report.fetched == 10
        assert report.upserted == 15


# ---------------------------------------------------------------------------
# IngestionPipeline — basic flow
# ---------------------------------------------------------------------------


class TestIngestionPipelineBasic:
    def test_empty_connector_yields_empty_report(self) -> None:
        conn = FakeConnector("c", [])
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)
        report = asyncio.run(pipeline.ingest())
        assert report.fetched == 0
        assert report.parsed == 0
        assert report.upserted == 0
        assert upserted == []

    def test_single_doc_single_chunk(self) -> None:
        conn = FakeConnector("c", _make_docs("hello world"))
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)
        report = asyncio.run(pipeline.ingest())
        assert report.fetched == 1
        assert report.parsed == 1
        assert report.skipped == 0
        assert report.upserted == 1
        assert upserted == ["hello world"]

    def test_multiple_docs(self) -> None:
        conn = FakeConnector("c", _make_docs("alpha", "beta", "gamma"))
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)
        report = asyncio.run(pipeline.ingest())
        assert report.fetched == 3
        assert report.parsed == 3
        assert report.upserted == 3
        assert upserted == ["alpha", "beta", "gamma"]

    def test_multi_chunk_per_doc(self) -> None:
        conn = FakeConnector("c", _make_docs("line1\nline2\nline3"))
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _split_chunker, upserted.append)
        report = asyncio.run(pipeline.ingest())
        assert report.fetched == 1
        assert report.parsed == 1
        assert report.upserted == 3
        assert upserted == ["line1", "line2", "line3"]

    def test_empty_chunker_produces_no_upserts(self) -> None:
        conn = FakeConnector("c", _make_docs("content"))
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _empty_chunker, upserted.append)
        report = asyncio.run(pipeline.ingest())
        assert report.parsed == 1
        assert report.upserted == 0
        assert upserted == []


# ---------------------------------------------------------------------------
# IngestionPipeline — deduplication
# ---------------------------------------------------------------------------


class TestIngestionPipelineDedup:
    def test_duplicate_doc_in_same_run_skipped(self) -> None:
        docs = [
            Document(doc_id="a", content="same content"),
            Document(doc_id="b", content="same content"),
        ]
        conn = FakeConnector("c", docs)
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)
        report = asyncio.run(pipeline.ingest())
        assert report.fetched == 2
        assert report.parsed == 1
        assert report.skipped == 1
        assert report.upserted == 1

    def test_duplicate_across_runs_skipped(self) -> None:
        docs = _make_docs("hello")
        conn = FakeConnector("c", docs)
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)
        report1 = asyncio.run(pipeline.ingest())
        assert report1.upserted == 1
        # Second run with same content
        conn2 = FakeConnector("c", docs)
        pipeline._connector = conn2  # swap connector, keep same pipeline (same seen set)
        report2 = asyncio.run(pipeline.ingest())
        assert report2.fetched == 1
        assert report2.skipped == 1
        assert report2.upserted == 0

    def test_different_content_not_skipped(self) -> None:
        docs = _make_docs("alpha", "beta")
        conn = FakeConnector("c", docs)
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)
        report = asyncio.run(pipeline.ingest())
        assert report.skipped == 0
        assert report.upserted == 2

    def test_seen_count_tracks_unique_hashes(self) -> None:
        docs = _make_docs("a", "b", "a")  # "a" appears twice
        conn = FakeConnector("c", docs)
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, lambda _: None)
        asyncio.run(pipeline.ingest())
        assert pipeline.seen_count == 2  # only "a" and "b"

    def test_reset_dedup_clears_seen_hashes(self) -> None:
        docs = _make_docs("hello")
        conn = FakeConnector("c", docs)
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)
        asyncio.run(pipeline.ingest())
        assert pipeline.seen_count == 1
        pipeline.reset_dedup()
        assert pipeline.seen_count == 0
        # After reset, same content is no longer skipped
        conn2 = FakeConnector("c", docs)
        pipeline._connector = conn2
        report = asyncio.run(pipeline.ingest())
        assert report.skipped == 0
        assert report.upserted == 1


# ---------------------------------------------------------------------------
# IngestionPipeline — incremental fetch
# ---------------------------------------------------------------------------


class TestIngestionPipelineIncremental:
    def test_since_cursor_passed_to_connector(self) -> None:
        docs = [Document(doc_id=str(i), content=f"doc{i}") for i in range(5)]
        conn = FakeConnector("c", docs)
        upserted: list[str] = []
        pipeline = IngestionPipeline(conn, TextParser(), _identity_chunker, upserted.append)
        report = asyncio.run(pipeline.ingest(since_cursor=2))
        assert report.fetched == 2  # docs 3 and 4 (cursor > 2)
        assert upserted == ["doc3", "doc4"]


# ---------------------------------------------------------------------------
# IngestionPipeline — error handling
# ---------------------------------------------------------------------------


class TestIngestionPipelineErrors:
    def test_parse_error_recorded_in_report(self) -> None:
        class BrokenParser:
            def parse(self, content, metadata=None, *, doc_id=""):
                raise ValueError("cannot parse")

        conn = FakeConnector("c", _make_docs("x"))
        pipeline = IngestionPipeline(
            conn, BrokenParser(), _identity_chunker, lambda _: None
        )
        report = asyncio.run(pipeline.ingest())
        assert report.fetched == 1
        assert report.parsed == 0
        assert len(report.errors) == 1
        assert "parse error" in report.errors[0]

    def test_good_doc_after_bad_doc_processed(self) -> None:
        class SelectiveParser:
            def parse(self, content, metadata=None, *, doc_id=""):
                if content == "bad":
                    raise ValueError("bad content")
                return ParsedDocument(doc_id=doc_id, text=content)

        docs = [
            Document(doc_id="0", content="bad"),
            Document(doc_id="1", content="good"),
        ]
        conn = FakeConnector("c", docs)
        upserted: list[str] = []
        pipeline = IngestionPipeline(
            conn, SelectiveParser(), _identity_chunker, upserted.append
        )
        report = asyncio.run(pipeline.ingest())
        assert report.fetched == 2
        assert report.parsed == 1
        assert len(report.errors) == 1
        assert upserted == ["good"]
