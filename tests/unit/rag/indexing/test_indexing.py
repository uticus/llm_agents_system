"""Unit tests for rag/indexing: IndexReport, Indexer."""

from __future__ import annotations

from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.indexing import Indexer, IndexReport
from llm_agents.rag.vector_store import InMemoryVectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_indexer(dims: int = 4) -> tuple[Indexer, FakeEmbedder, InMemoryVectorStore]:
    embedder = FakeEmbedder(dimensions=dims)
    store = InMemoryVectorStore()
    indexer = Indexer(embedder, store)
    return indexer, embedder, store


def _line_chunker(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# IndexReport
# ---------------------------------------------------------------------------


class TestIndexReport:
    def test_defaults(self) -> None:
        r = IndexReport()
        assert r.docs_indexed == 0
        assert r.chunks_added == 0
        assert r.chunks_skipped == 0
        assert r.errors == []

    def test_construction(self) -> None:
        r = IndexReport(docs_indexed=3, chunks_added=12, chunks_skipped=2)
        assert r.docs_indexed == 3
        assert r.chunks_added == 12
        assert r.chunks_skipped == 2


# ---------------------------------------------------------------------------
# Indexer — single document
# ---------------------------------------------------------------------------


class TestIndexerSingleDoc:
    def test_single_chunk_default_chunker(self) -> None:
        indexer, embedder, store = _make_indexer()
        report = indexer.index("d1", "hello world")
        assert report.docs_indexed == 1
        assert report.chunks_added == 1
        assert len(store) == 1
        assert embedder.embed_count == 1

    def test_chunk_id_format(self) -> None:
        indexer, _, store = _make_indexer()
        indexer.index("myDoc", "text")
        assert "myDoc#0" in store

    def test_multi_chunk(self) -> None:
        indexer, embedder, store = _make_indexer()
        indexer2 = Indexer(embedder, store, chunker=_line_chunker)
        report = indexer2.index("d1", "line1\nline2\nline3")
        assert report.chunks_added == 3
        assert len(store) == 3

    def test_chunk_metadata_contains_doc_id(self) -> None:
        indexer, _, store = _make_indexer()
        indexer.index("doc42", "some text", metadata={"source": "wiki"})
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=1)
        assert results[0].metadata["doc_id"] == "doc42"

    def test_chunk_metadata_contains_chunk_index(self) -> None:
        embedder = FakeEmbedder(dimensions=4)
        store = InMemoryVectorStore()
        indexer = Indexer(embedder, store, chunker=_line_chunker)
        indexer.index("d1", "line1\nline2")
        results = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        indices = {r.metadata["chunk_index"] for r in results}
        assert indices == {0, 1}


# ---------------------------------------------------------------------------
# Indexer — deduplication
# ---------------------------------------------------------------------------


class TestIndexerDedup:
    def test_same_text_second_index_skipped(self) -> None:
        indexer, embedder, store = _make_indexer()
        indexer.index("d1", "hello")
        report2 = indexer.index("d1", "hello")
        assert report2.chunks_skipped == 1
        assert report2.chunks_added == 0
        assert embedder.embed_count == 1  # no second embed call

    def test_different_text_not_skipped(self) -> None:
        indexer, embedder, store = _make_indexer()
        indexer.index("d1", "hello")
        report2 = indexer.index("d2", "world")
        assert report2.chunks_skipped == 0
        assert report2.chunks_added == 1

    def test_seen_count_tracks_unique_chunks(self) -> None:
        indexer, _, _ = _make_indexer()
        indexer.index("d1", "alpha")
        indexer.index("d2", "beta")
        indexer.index("d3", "alpha")  # duplicate
        assert indexer.seen_count == 2

    def test_reset_dedup_clears_seen(self) -> None:
        indexer, embedder, store = _make_indexer()
        indexer.index("d1", "hello")
        indexer.reset_dedup()
        assert indexer.seen_count == 0
        report = indexer.index("d1", "hello")
        assert report.chunks_added == 1  # not skipped after reset


# ---------------------------------------------------------------------------
# Indexer — batch
# ---------------------------------------------------------------------------


class TestIndexerBatch:
    def test_batch_aggregates_counts(self) -> None:
        indexer, _, store = _make_indexer()
        report = indexer.index_batch([("d1", "alpha"), ("d2", "beta"), ("d3", "gamma")])
        assert report.docs_indexed == 3
        assert report.chunks_added == 3
        assert len(store) == 3

    def test_batch_empty(self) -> None:
        indexer, _, _ = _make_indexer()
        report = indexer.index_batch([])
        assert report.docs_indexed == 0
        assert report.chunks_added == 0

    def test_batch_dedup_across_docs(self) -> None:
        indexer, embedder, _ = _make_indexer()
        report = indexer.index_batch([("d1", "same"), ("d2", "same")])
        assert report.chunks_added == 1
        assert report.chunks_skipped == 1
        assert embedder.embed_count == 1


# ---------------------------------------------------------------------------
# Indexer — error handling
# ---------------------------------------------------------------------------


class TestIndexerErrors:
    def test_embed_error_captured_in_report(self) -> None:
        class FailEmbedder:
            dimensions = 4

            def embed(self, texts):
                raise RuntimeError("embed failed")

        store = InMemoryVectorStore()
        indexer = Indexer(FailEmbedder(), store)
        report = indexer.index("d1", "hello")
        assert len(report.errors) == 1
        assert "embed error" in report.errors[0]
        assert len(store) == 0
