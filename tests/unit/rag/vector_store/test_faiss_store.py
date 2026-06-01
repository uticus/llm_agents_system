"""Unit tests for rag/vector_store: FAISSVectorStore."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("faiss", reason="faiss-cpu not installed; skipping FAISS tests")

from llm_agents.rag.vector_store import FAISSVectorStore, SearchResult, VectorStore  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit(dims: int, hot: int) -> list[float]:
    """Return a unit vector with a 1.0 at position *hot* and 0.0 elsewhere."""
    v = [0.0] * dims
    v[hot] = 1.0
    return v


def _norm(v: list[float]) -> list[float]:
    """L2-normalise a vector."""
    mag = math.sqrt(sum(x * x for x in v))
    return [x / mag for x in v] if mag > 0 else v


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestFAISSVectorStoreProtocol:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(FAISSVectorStore(), VectorStore)

    def test_returns_search_result_instances(self) -> None:
        store = FAISSVectorStore()
        store.upsert("a", _unit(4, 0))
        results = store.search(_unit(4, 0), top_k=1)
        assert all(isinstance(r, SearchResult) for r in results)


# ---------------------------------------------------------------------------
# Basic upsert / search
# ---------------------------------------------------------------------------


class TestFAISSVectorStoreSearch:
    def test_empty_store_returns_empty(self) -> None:
        store = FAISSVectorStore()
        assert store.search(_unit(4, 0)) == []

    def test_single_upsert_and_search(self) -> None:
        store = FAISSVectorStore()
        store.upsert("doc1", _unit(4, 0))
        results = store.search(_unit(4, 0), top_k=1)
        assert len(results) == 1
        assert results[0].doc_id == "doc1"

    def test_top_k_limits_results(self) -> None:
        store = FAISSVectorStore()
        for i in range(5):
            store.upsert(f"doc{i}", _unit(5, i))
        results = store.search(_unit(5, 0), top_k=3)
        assert len(results) <= 3

    def test_top_k_larger_than_store_returns_all(self) -> None:
        store = FAISSVectorStore()
        store.upsert("a", _unit(3, 0))
        store.upsert("b", _unit(3, 1))
        results = store.search(_unit(3, 0), top_k=100)
        assert len(results) == 2

    def test_nearest_neighbour_ranked_first(self) -> None:
        store = FAISSVectorStore()
        store.upsert("close", _unit(4, 0))  # identical direction
        store.upsert("far", _unit(4, 1))  # orthogonal
        results = store.search(_unit(4, 0), top_k=2)
        assert results[0].doc_id == "close"

    def test_scores_descending(self) -> None:
        store = FAISSVectorStore()
        store.upsert("a", _unit(4, 0))
        store.upsert("b", _unit(4, 1))
        store.upsert("c", _unit(4, 2))
        results = store.search(_unit(4, 0), top_k=3)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_identical_vector_score_near_one(self) -> None:
        store = FAISSVectorStore()
        v = _norm([1.0, 2.0, 3.0])
        store.upsert("doc", v)
        results = store.search(v, top_k=1)
        assert results[0].score == pytest.approx(1.0, abs=1e-5)

    def test_orthogonal_vectors_score_near_zero(self) -> None:
        store = FAISSVectorStore()
        store.upsert("a", _unit(2, 0))  # [1, 0]
        store.upsert("b", _unit(2, 1))  # [0, 1]
        results = store.search(_unit(2, 0), top_k=2)
        by_id = {r.doc_id: r.score for r in results}
        assert by_id["a"] == pytest.approx(1.0, abs=1e-5)
        assert by_id["b"] == pytest.approx(0.0, abs=1e-5)


# ---------------------------------------------------------------------------
# Upsert semantics (update)
# ---------------------------------------------------------------------------


class TestFAISSVectorStoreUpsert:
    def test_upsert_updates_existing(self) -> None:
        store = FAISSVectorStore()
        store.upsert("doc", _unit(4, 0))
        store.upsert("doc", _unit(4, 1))  # change direction
        results = store.search(_unit(4, 1), top_k=1)
        assert results[0].doc_id == "doc"
        assert results[0].score == pytest.approx(1.0, abs=1e-5)

    def test_upsert_updates_metadata(self) -> None:
        store = FAISSVectorStore()
        store.upsert("doc", _unit(4, 0), {"v": 1})
        store.upsert("doc", _unit(4, 0), {"v": 2})
        results = store.search(_unit(4, 0), top_k=1)
        assert results[0].metadata["v"] == 2

    def test_dimension_mismatch_raises(self) -> None:
        store = FAISSVectorStore()
        store.upsert("doc", _unit(4, 0))
        with pytest.raises(ValueError, match="dimensionality"):
            store.upsert("doc2", _unit(3, 0))


# ---------------------------------------------------------------------------
# Metadata passthrough
# ---------------------------------------------------------------------------


class TestFAISSVectorStoreMetadata:
    def test_metadata_returned_in_results(self) -> None:
        store = FAISSVectorStore()
        store.upsert("doc", _unit(4, 0), {"source": "wiki", "page": 42})
        results = store.search(_unit(4, 0), top_k=1)
        assert results[0].metadata["source"] == "wiki"
        assert results[0].metadata["page"] == 42

    def test_no_metadata_defaults_to_empty_dict(self) -> None:
        store = FAISSVectorStore()
        store.upsert("doc", _unit(4, 0))
        results = store.search(_unit(4, 0), top_k=1)
        assert results[0].metadata == {}

    def test_metadata_is_copied_not_shared(self) -> None:
        store = FAISSVectorStore()
        meta = {"k": "v"}
        store.upsert("doc", _unit(4, 0), meta)
        meta["k"] = "mutated"
        results = store.search(_unit(4, 0), top_k=1)
        assert results[0].metadata["k"] == "v"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestFAISSVectorStoreDelete:
    def test_delete_existing_returns_true(self) -> None:
        store = FAISSVectorStore()
        store.upsert("doc", _unit(4, 0))
        assert store.delete("doc") is True

    def test_delete_missing_returns_false(self) -> None:
        store = FAISSVectorStore()
        assert store.delete("nonexistent") is False

    def test_deleted_doc_absent_from_search(self) -> None:
        store = FAISSVectorStore()
        store.upsert("keep", _unit(4, 0))
        store.upsert("drop", _unit(4, 0))
        store.delete("drop")
        results = store.search(_unit(4, 0), top_k=10)
        assert all(r.doc_id != "drop" for r in results)

    def test_delete_then_upsert_same_id(self) -> None:
        store = FAISSVectorStore()
        store.upsert("doc", _unit(4, 0))
        store.delete("doc")
        store.upsert("doc", _unit(4, 1))
        results = store.search(_unit(4, 1), top_k=1)
        assert results[0].doc_id == "doc"
        assert results[0].score == pytest.approx(1.0, abs=1e-5)

    def test_search_after_all_deleted_returns_empty(self) -> None:
        store = FAISSVectorStore()
        store.upsert("a", _unit(4, 0))
        store.delete("a")
        assert store.search(_unit(4, 0)) == []


# ---------------------------------------------------------------------------
# Inspection helpers
# ---------------------------------------------------------------------------


class TestFAISSVectorStoreInspection:
    def test_len_empty(self) -> None:
        assert len(FAISSVectorStore()) == 0

    def test_len_after_upserts(self) -> None:
        store = FAISSVectorStore()
        store.upsert("a", _unit(3, 0))
        store.upsert("b", _unit(3, 1))
        assert len(store) == 2

    def test_len_after_delete(self) -> None:
        store = FAISSVectorStore()
        store.upsert("a", _unit(3, 0))
        store.delete("a")
        assert len(store) == 0

    def test_contains_true(self) -> None:
        store = FAISSVectorStore()
        store.upsert("a", _unit(3, 0))
        assert "a" in store

    def test_contains_false(self) -> None:
        assert "x" not in FAISSVectorStore()


# ---------------------------------------------------------------------------
# Deferred import — module import must not require faiss
# ---------------------------------------------------------------------------


class TestFAISSVectorStoreDeferredImport:
    def test_module_importable_without_triggering_faiss_at_class_level(self) -> None:
        """Importing FAISSVectorStore should not immediately import faiss.

        We verify this by checking that constructing the class does not call
        into the faiss module (faiss is only touched inside _build_index /
        search, not in __init__).
        """
        from unittest.mock import patch

        with patch.dict("sys.modules", {"faiss": None}):
            # Re-importing the class definition should not raise even if
            # sys.modules["faiss"] is poisoned — faiss is deferred.
            import importlib

            import llm_agents.rag.vector_store._faiss_store as mod

            importlib.reload(mod)
            store = mod.FAISSVectorStore()
            store.upsert("x", [1.0, 0.0])
            # search() triggers _build_index() which imports faiss;
            # faiss is restored in sys.modules by importorskip at module level,
            # so after the patch context exits search works fine.
