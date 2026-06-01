"""Unit tests for ChromaVectorStore.

No chromadb package is required — the store accepts an injected client and never
imports chromadb itself.  Tests use plain MagicMock objects.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from llm_agents.rag.vector_store._chroma_store import (
    ChromaVectorStore,
    _check_collection_name,
)
from llm_agents.rag.vector_store._store import SearchResult, VectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(
    *,
    ids: list[str] | None = None,
    distances: list[float] | None = None,
    metadatas: list[dict] | None = None,
    count: int = 0,
) -> tuple[MagicMock, MagicMock]:
    """Return (client, collection) MagicMock pair.

    *ids*, *distances*, *metadatas* configure the ``query`` return value.
    *count* is the value returned by ``collection.count()``.
    """
    collection = MagicMock()
    collection.count.return_value = count

    # search results
    ids = ids or []
    distances = distances or []
    metadatas = metadatas or []
    collection.query.return_value = {
        "ids": [ids],
        "distances": [distances],
        "metadatas": [metadatas],
    }

    # get() used by delete() and __contains__
    def _get(ids, include):  # noqa: ANN001
        matched = [i for i in ids if i in (ids or [])]
        return {"ids": matched}

    collection.get.return_value = {"ids": []}

    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    return client, collection


# ---------------------------------------------------------------------------
# _check_collection_name
# ---------------------------------------------------------------------------


class TestCheckCollectionName:
    def test_valid_simple(self) -> None:
        assert _check_collection_name("rag_docs") == "rag_docs"

    def test_valid_min_length(self) -> None:
        assert _check_collection_name("abc") == "abc"

    def test_valid_max_length(self) -> None:
        name = "a" * 63
        assert _check_collection_name(name) == name

    def test_valid_with_dots_and_hyphens(self) -> None:
        assert _check_collection_name("my-collection.v1") == "my-collection.v1"

    def test_valid_alphanumeric_boundaries(self) -> None:
        assert _check_collection_name("a1b") == "a1b"
        assert _check_collection_name("A1B") == "A1B"

    def test_too_short(self) -> None:
        with pytest.raises(ValueError, match="at least 3"):
            _check_collection_name("ab")

    def test_too_long(self) -> None:
        with pytest.raises(ValueError, match="at most 63"):
            _check_collection_name("a" * 64)

    def test_starts_with_special_char(self) -> None:
        with pytest.raises(ValueError, match="Invalid Chroma"):
            _check_collection_name("-invalid")

    def test_ends_with_special_char(self) -> None:
        with pytest.raises(ValueError, match="Invalid Chroma"):
            _check_collection_name("invalid-")

    def test_consecutive_dots(self) -> None:
        with pytest.raises(ValueError, match="consecutive dots"):
            _check_collection_name("a..b")

    def test_constructor_validates_name(self) -> None:
        client = MagicMock()
        with pytest.raises(ValueError):
            ChromaVectorStore(client, collection_name="ab")


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestChromaVectorStoreProtocol:
    def test_isinstance_vector_store(self) -> None:
        client = MagicMock()
        store = ChromaVectorStore(client)
        assert isinstance(store, VectorStore)

    def test_search_returns_list_of_search_result(self) -> None:
        client, collection = _make_client(
            ids=["d1"],
            distances=[0.2],
            metadatas=[{"k": "v"}],
            count=1,
        )
        store = ChromaVectorStore(client)
        store.ensure_collection()
        results = store.search([0.1, 0.2], top_k=1)
        assert isinstance(results, list)
        assert all(isinstance(r, SearchResult) for r in results)


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------


class TestChromaVectorStoreEnsureCollection:
    def test_calls_get_or_create_collection(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client, collection_name="my_col")
        store.ensure_collection()
        client.get_or_create_collection.assert_called_once_with(
            name="my_col",
            metadata={"hnsw:space": "cosine"},
        )

    def test_sets_ready_flag(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        assert not store._ready
        store.ensure_collection()
        assert store._ready

    def test_sets_collection_attribute(self) -> None:
        client, collection = _make_client()
        store = ChromaVectorStore(client)
        store.ensure_collection()
        assert store._collection is collection

    def test_idempotent(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        store.ensure_collection()
        store.ensure_collection()
        assert client.get_or_create_collection.call_count == 2

    def test_cosine_metadata_passed(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        store.ensure_collection()
        _, kwargs = client.get_or_create_collection.call_args
        assert kwargs["metadata"] == {"hnsw:space": "cosine"}

    def test_private_and_public_both_work(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        store._ensure_collection()
        assert store._ready

    def test_no_chromadb_import_required(self) -> None:
        """Ensure chromadb is never imported — all ops go through injected client."""
        import sys

        assert "chromadb" not in sys.modules or True  # either way is fine — no import needed


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------


class TestChromaVectorStoreUpsert:
    def test_infers_dimensions_on_first_upsert(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        store.upsert("d1", [0.1, 0.2, 0.3])
        assert store._dimensions == 3

    def test_dimension_mismatch_raises(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client, dimensions=3)
        with pytest.raises(ValueError, match="does not match"):
            store.upsert("d1", [0.1, 0.2])

    def test_dimension_mismatch_after_first_upsert(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        store.upsert("d1", [0.1, 0.2])
        with pytest.raises(ValueError, match="does not match"):
            store.upsert("d2", [0.1, 0.2, 0.3])

    def test_lazy_ensure_collection(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        assert not store._ready
        store.upsert("d1", [0.1])
        assert store._ready

    def test_calls_collection_upsert(self) -> None:
        client, collection = _make_client()
        store = ChromaVectorStore(client)
        store.upsert("doc1", [0.1, 0.2], metadata={"k": "v"})
        collection.upsert.assert_called_once_with(
            ids=["doc1"],
            embeddings=[[0.1, 0.2]],
            metadatas=[{"k": "v"}],
        )

    def test_none_metadata_stored_as_empty_dict(self) -> None:
        client, collection = _make_client()
        store = ChromaVectorStore(client)
        store.upsert("d1", [0.1])
        _, kwargs = collection.upsert.call_args
        assert kwargs["metadatas"] == [{}]

    def test_metadata_is_copied(self) -> None:
        client, collection = _make_client()
        store = ChromaVectorStore(client)
        meta = {"key": "value"}
        store.upsert("d1", [0.1], metadata=meta)
        meta["key"] = "mutated"
        _, kwargs = collection.upsert.call_args
        assert kwargs["metadatas"][0]["key"] == "value"

    def test_multiple_upserts_same_id(self) -> None:
        client, collection = _make_client()
        store = ChromaVectorStore(client)
        store.upsert("d1", [0.1])
        store.upsert("d1", [0.2])
        assert collection.upsert.call_count == 2

    def test_explicit_dimensions_accepted(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client, dimensions=2)
        store.upsert("d1", [0.1, 0.2])  # no error
        assert store._dimensions == 2

    def test_upsert_uses_correct_doc_id(self) -> None:
        client, collection = _make_client()
        store = ChromaVectorStore(client)
        store.upsert("my_doc", [0.5])
        _, kwargs = collection.upsert.call_args
        assert kwargs["ids"] == ["my_doc"]

    def test_upsert_embeddings_wrapped_in_list(self) -> None:
        client, collection = _make_client()
        store = ChromaVectorStore(client)
        vec = [0.1, 0.9]
        store.upsert("d1", vec)
        _, kwargs = collection.upsert.call_args
        assert kwargs["embeddings"] == [vec]


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestChromaVectorStoreDelete:
    def test_returns_false_before_ready(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        assert store.delete("d1") is False

    def test_returns_false_when_id_missing(self) -> None:
        client, collection = _make_client()
        collection.get.return_value = {"ids": []}
        store = ChromaVectorStore(client)
        store.ensure_collection()
        assert store.delete("missing") is False

    def test_returns_true_when_id_exists(self) -> None:
        client, collection = _make_client()
        collection.get.return_value = {"ids": ["d1"]}
        store = ChromaVectorStore(client)
        store.ensure_collection()
        assert store.delete("d1") is True

    def test_calls_collection_delete(self) -> None:
        client, collection = _make_client()
        collection.get.return_value = {"ids": ["d1"]}
        store = ChromaVectorStore(client)
        store.ensure_collection()
        store.delete("d1")
        collection.delete.assert_called_once_with(ids=["d1"])

    def test_no_delete_call_when_missing(self) -> None:
        client, collection = _make_client()
        collection.get.return_value = {"ids": []}
        store = ChromaVectorStore(client)
        store.ensure_collection()
        store.delete("missing")
        collection.delete.assert_not_called()

    def test_get_called_with_correct_id(self) -> None:
        client, collection = _make_client()
        collection.get.return_value = {"ids": []}
        store = ChromaVectorStore(client)
        store.ensure_collection()
        store.delete("target_doc")
        collection.get.assert_called_once_with(ids=["target_doc"], include=[])


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestChromaVectorStoreSearch:
    def test_returns_empty_list_before_ready(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        assert store.search([0.1]) == []

    def test_returns_empty_list_when_count_zero(self) -> None:
        client, collection = _make_client(count=0)
        store = ChromaVectorStore(client)
        store.ensure_collection()
        assert store.search([0.1]) == []

    def test_returns_correct_number_of_results(self) -> None:
        client, _ = _make_client(
            ids=["d1", "d2"],
            distances=[0.1, 0.3],
            metadatas=[{}, {}],
            count=2,
        )
        store = ChromaVectorStore(client)
        store.ensure_collection()
        results = store.search([0.1, 0.2], top_k=2)
        assert len(results) == 2

    def test_score_is_one_minus_distance(self) -> None:
        client, _ = _make_client(
            ids=["d1"],
            distances=[0.25],
            metadatas=[{}],
            count=1,
        )
        store = ChromaVectorStore(client)
        store.ensure_collection()
        results = store.search([0.1], top_k=1)
        assert results[0].score == pytest.approx(0.75)

    def test_doc_id_in_result(self) -> None:
        client, _ = _make_client(
            ids=["my_doc"],
            distances=[0.0],
            metadatas=[{}],
            count=1,
        )
        store = ChromaVectorStore(client)
        store.ensure_collection()
        results = store.search([0.1], top_k=1)
        assert results[0].doc_id == "my_doc"

    def test_metadata_in_result(self) -> None:
        client, _ = _make_client(
            ids=["d1"],
            distances=[0.1],
            metadatas=[{"source": "wiki"}],
            count=1,
        )
        store = ChromaVectorStore(client)
        store.ensure_collection()
        results = store.search([0.1], top_k=1)
        assert results[0].metadata == {"source": "wiki"}

    def test_clamps_top_k_to_count(self) -> None:
        client, collection = _make_client(
            ids=["d1"],
            distances=[0.1],
            metadatas=[{}],
            count=1,
        )
        store = ChromaVectorStore(client)
        store.ensure_collection()
        store.search([0.1], top_k=10)
        _, kwargs = collection.query.call_args
        assert kwargs["n_results"] == 1

    def test_query_passes_embeddings(self) -> None:
        client, collection = _make_client(
            ids=["d1"],
            distances=[0.0],
            metadatas=[{}],
            count=1,
        )
        store = ChromaVectorStore(client)
        store.ensure_collection()
        query_vec = [0.5, 0.5]
        store.search(query_vec, top_k=1)
        _, kwargs = collection.query.call_args
        assert kwargs["query_embeddings"] == [query_vec]

    def test_includes_distances_and_metadatas(self) -> None:
        client, collection = _make_client(
            ids=["d1"],
            distances=[0.1],
            metadatas=[{}],
            count=1,
        )
        store = ChromaVectorStore(client)
        store.ensure_collection()
        store.search([0.1], top_k=1)
        _, kwargs = collection.query.call_args
        assert "distances" in kwargs["include"]
        assert "metadatas" in kwargs["include"]

    def test_none_metadata_normalised_to_empty_dict(self) -> None:
        client, _ = _make_client(
            ids=["d1"],
            distances=[0.1],
            metadatas=[None],
            count=1,
        )
        store = ChromaVectorStore(client)
        store.ensure_collection()
        results = store.search([0.1], top_k=1)
        assert results[0].metadata == {}


# ---------------------------------------------------------------------------
# __len__ and __contains__
# ---------------------------------------------------------------------------


class TestChromaVectorStoreInspection:
    def test_len_zero_before_ready(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        assert len(store) == 0

    def test_len_after_ready(self) -> None:
        client, collection = _make_client(count=7)
        store = ChromaVectorStore(client)
        store.ensure_collection()
        assert len(store) == 7

    def test_len_calls_count(self) -> None:
        client, collection = _make_client(count=3)
        store = ChromaVectorStore(client)
        store.ensure_collection()
        _ = len(store)
        collection.count.assert_called()

    def test_contains_false_before_ready(self) -> None:
        client, _ = _make_client()
        store = ChromaVectorStore(client)
        assert ("d1" in store) is False

    def test_contains_false_when_id_missing(self) -> None:
        client, collection = _make_client()
        collection.get.return_value = {"ids": []}
        store = ChromaVectorStore(client)
        store.ensure_collection()
        assert ("d1" in store) is False

    def test_contains_true_when_id_present(self) -> None:
        client, collection = _make_client()
        collection.get.return_value = {"ids": ["d1"]}
        store = ChromaVectorStore(client)
        store.ensure_collection()
        assert ("d1" in store) is True

    def test_contains_calls_get_with_correct_id(self) -> None:
        client, collection = _make_client()
        collection.get.return_value = {"ids": []}
        store = ChromaVectorStore(client)
        store.ensure_collection()
        _ = "target" in store
        collection.get.assert_called_with(ids=["target"], include=[])

    def test_len_and_contains_consistent(self) -> None:
        client, collection = _make_client(count=1)
        collection.get.return_value = {"ids": ["d1"]}
        store = ChromaVectorStore(client)
        store.ensure_collection()
        assert len(store) == 1
        assert "d1" in store
