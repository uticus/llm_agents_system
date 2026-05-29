"""Unit tests for rag/vector_store: SearchResult, VectorStore, InMemoryVectorStore."""

from __future__ import annotations

import math

import pytest

from llm_agents.rag.vector_store import InMemoryVectorStore, SearchResult, VectorStore


# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------


class TestSearchResult:
    def test_construction(self) -> None:
        r = SearchResult(doc_id="d1", score=0.9)
        assert r.doc_id == "d1"
        assert r.score == 0.9
        assert r.metadata == {}

    def test_with_metadata(self) -> None:
        r = SearchResult(doc_id="d2", score=0.7, metadata={"title": "x"})
        assert r.metadata == {"title": "x"}


# ---------------------------------------------------------------------------
# VectorStore protocol
# ---------------------------------------------------------------------------


class TestVectorStoreProtocol:
    def test_in_memory_satisfies_protocol(self) -> None:
        store = InMemoryVectorStore()
        assert isinstance(store, VectorStore)

    def test_plain_class_satisfies_protocol(self) -> None:
        class MyStore:
            def upsert(self, doc_id, vector, metadata=None) -> None:
                pass

            def search(self, query_vector, top_k=5):
                return []

            def delete(self, doc_id) -> bool:
                return False

        assert isinstance(MyStore(), VectorStore)

    def test_missing_upsert_fails_protocol(self) -> None:
        class Bad:
            def search(self, query_vector, top_k=5):
                return []

            def delete(self, doc_id) -> bool:
                return False

        assert not isinstance(Bad(), VectorStore)


# ---------------------------------------------------------------------------
# InMemoryVectorStore — upsert and containment
# ---------------------------------------------------------------------------


class TestInMemoryVectorStoreUpsert:
    def test_upsert_increases_length(self) -> None:
        store = InMemoryVectorStore()
        assert len(store) == 0
        store.upsert("a", [1.0, 0.0])
        assert len(store) == 1

    def test_contains_after_upsert(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0])
        assert "a" in store

    def test_not_contains_before_upsert(self) -> None:
        store = InMemoryVectorStore()
        assert "x" not in store

    def test_upsert_overwrites(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0])
        store.upsert("a", [0.0, 1.0])
        assert len(store) == 1

    def test_upsert_metadata_stored(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0], metadata={"tag": "x"})
        results = store.search([1.0, 0.0])
        assert results[0].metadata == {"tag": "x"}

    def test_upsert_metadata_none_gives_empty_dict(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0])
        results = store.search([1.0, 0.0])
        assert results[0].metadata == {}

    def test_metadata_isolation(self) -> None:
        store = InMemoryVectorStore()
        meta = {"k": "v"}
        store.upsert("a", [1.0, 0.0], metadata=meta)
        meta["extra"] = "x"
        results = store.search([1.0, 0.0])
        assert "extra" not in results[0].metadata


# ---------------------------------------------------------------------------
# InMemoryVectorStore — delete
# ---------------------------------------------------------------------------


class TestInMemoryVectorStoreDelete:
    def test_delete_returns_true_when_exists(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0])
        assert store.delete("a") is True

    def test_delete_removes_entry(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0])
        store.delete("a")
        assert "a" not in store
        assert len(store) == 0

    def test_delete_returns_false_when_missing(self) -> None:
        store = InMemoryVectorStore()
        assert store.delete("nonexistent") is False

    def test_delete_does_not_affect_others(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0])
        store.upsert("b", [0.0, 1.0])
        store.delete("a")
        assert "b" in store


# ---------------------------------------------------------------------------
# InMemoryVectorStore — search
# ---------------------------------------------------------------------------


class TestInMemoryVectorStoreSearch:
    def test_empty_store_returns_empty(self) -> None:
        store = InMemoryVectorStore()
        assert store.search([1.0, 0.0]) == []

    def test_returns_at_most_top_k(self) -> None:
        store = InMemoryVectorStore()
        for i in range(10):
            store.upsert(str(i), [float(i), 0.0])
        results = store.search([1.0, 0.0], top_k=3)
        assert len(results) <= 3

    def test_results_sorted_descending(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0, 0.0])
        store.upsert("b", [0.0, 1.0, 0.0])
        store.upsert("c", [0.0, 0.0, 1.0])
        results = store.search([1.0, 0.0, 0.0])
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_exact_match_score_is_one(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0])
        results = store.search([1.0, 0.0])
        assert abs(results[0].score - 1.0) < 1e-9

    def test_orthogonal_vector_score_is_zero(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0])
        results = store.search([0.0, 1.0])
        assert abs(results[0].score) < 1e-9

    def test_top_k_larger_than_store(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0])
        results = store.search([1.0, 0.0], top_k=100)
        assert len(results) == 1

    def test_closest_doc_returned_first(self) -> None:
        store = InMemoryVectorStore()
        # "a" is aligned with query; "b" is orthogonal
        store.upsert("a", [1.0, 0.0])
        store.upsert("b", [0.0, 1.0])
        results = store.search([1.0, 0.0], top_k=2)
        assert results[0].doc_id == "a"

    def test_zero_vector_score_is_zero(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [0.0, 0.0])
        results = store.search([1.0, 0.0])
        assert results[0].score == 0.0

    def test_metadata_returned_in_results(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("a", [1.0, 0.0], metadata={"page": 1})
        results = store.search([1.0, 0.0])
        assert results[0].metadata == {"page": 1}
