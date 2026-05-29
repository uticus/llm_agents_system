"""Unit tests for rag/retrieval: RetrievedPassage, DenseRetriever."""

from __future__ import annotations

import pytest

from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.retrieval import DenseRetriever, RetrievedPassage
from llm_agents.rag.vector_store import InMemoryVectorStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_retriever(
    dims: int = 4,
    top_k: int = 5,
) -> tuple[DenseRetriever, FakeEmbedder, InMemoryVectorStore]:
    embedder = FakeEmbedder(dimensions=dims)
    store = InMemoryVectorStore()
    retriever = DenseRetriever(embedder, store, top_k=top_k)
    return retriever, embedder, store


def _seed_store(store: InMemoryVectorStore, n: int = 5, dims: int = 4) -> None:
    """Upsert n identical unit-ish vectors so search returns results."""
    for i in range(n):
        store.upsert(
            f"chunk#{i}",
            [1.0] + [0.0] * (dims - 1),
            metadata={"text": f"text {i}", "doc_id": f"doc{i}"},
        )


# ---------------------------------------------------------------------------
# RetrievedPassage
# ---------------------------------------------------------------------------


class TestRetrievedPassage:
    def test_defaults(self) -> None:
        p = RetrievedPassage(doc_id="d1")
        assert p.text == ""
        assert p.score == 0.0
        assert p.metadata == {}

    def test_full_construction(self) -> None:
        p = RetrievedPassage(doc_id="d1", text="hello", score=0.9, metadata={"k": "v"})
        assert p.text == "hello"
        assert p.score == 0.9
        assert p.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# DenseRetriever — construction
# ---------------------------------------------------------------------------


class TestDenseRetrieverConstruction:
    def test_invalid_top_k_raises(self) -> None:
        with pytest.raises(ValueError):
            DenseRetriever(FakeEmbedder(), InMemoryVectorStore(), top_k=0)

    def test_default_top_k(self) -> None:
        retriever, _, _ = _make_retriever()
        assert retriever.top_k == 5


# ---------------------------------------------------------------------------
# DenseRetriever — retrieve
# ---------------------------------------------------------------------------


class TestDenseRetrieverRetrieve:
    def test_empty_store_returns_empty(self) -> None:
        retriever, _, _ = _make_retriever()
        results = retriever.retrieve("hello")
        assert results == []

    def test_returns_results_up_to_top_k(self) -> None:
        retriever, _, store = _make_retriever(top_k=3)
        _seed_store(store, n=10)
        results = retriever.retrieve("query")
        assert len(results) <= 3

    def test_results_are_retrieved_passages(self) -> None:
        retriever, _, store = _make_retriever()
        _seed_store(store, n=2)
        results = retriever.retrieve("query")
        for r in results:
            assert isinstance(r, RetrievedPassage)

    def test_sorted_by_descending_score(self) -> None:
        retriever, _, store = _make_retriever()
        _seed_store(store, n=5)
        results = retriever.retrieve("query")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_text_from_metadata(self) -> None:
        retriever, _, store = _make_retriever()
        store.upsert("c1", [1.0, 0.0, 0.0, 0.0], metadata={"text": "hello world"})
        results = retriever.retrieve("query")
        assert results[0].text == "hello world"

    def test_missing_text_in_metadata_gives_empty_string(self) -> None:
        retriever, _, store = _make_retriever()
        store.upsert("c1", [1.0, 0.0, 0.0, 0.0], metadata={"doc_id": "d1"})
        results = retriever.retrieve("query")
        assert results[0].text == ""

    def test_per_call_top_k_override(self) -> None:
        retriever, _, store = _make_retriever(top_k=10)
        _seed_store(store, n=8)
        results = retriever.retrieve("query", top_k=2)
        assert len(results) <= 2

    def test_embedder_called_once_per_retrieve(self) -> None:
        retriever, embedder, store = _make_retriever()
        _seed_store(store, n=3)
        retriever.retrieve("q1")
        retriever.retrieve("q2")
        assert embedder.embed_count == 2


# ---------------------------------------------------------------------------
# DenseRetriever — metadata filters
# ---------------------------------------------------------------------------


class TestDenseRetrieverFilters:
    def test_filter_by_doc_id(self) -> None:
        retriever, _, store = _make_retriever()
        store.upsert("c0", [1.0, 0.0, 0.0, 0.0], metadata={"doc_id": "A"})
        store.upsert("c1", [1.0, 0.0, 0.0, 0.0], metadata={"doc_id": "B"})
        results = retriever.retrieve("q", filters={"doc_id": "A"})
        assert all(r.metadata["doc_id"] == "A" for r in results)
        assert len(results) == 1

    def test_filter_no_match_returns_empty(self) -> None:
        retriever, _, store = _make_retriever()
        store.upsert("c0", [1.0, 0.0, 0.0, 0.0], metadata={"doc_id": "A"})
        results = retriever.retrieve("q", filters={"doc_id": "Z"})
        assert results == []

    def test_multi_key_filter(self) -> None:
        retriever, _, store = _make_retriever()
        store.upsert(
            "c0",
            [1.0, 0.0, 0.0, 0.0],
            metadata={"doc_id": "A", "section": "intro"},
        )
        store.upsert(
            "c1",
            [1.0, 0.0, 0.0, 0.0],
            metadata={"doc_id": "A", "section": "body"},
        )
        results = retriever.retrieve(
            "q",
            filters={"doc_id": "A", "section": "intro"},
        )
        assert len(results) == 1
        assert results[0].metadata["section"] == "intro"

    def test_none_filter_returns_all(self) -> None:
        retriever, _, store = _make_retriever()
        _seed_store(store, n=4)
        results = retriever.retrieve("q", filters=None)
        assert len(results) == 4
