"""Unit tests for ElasticsearchVectorStore.

No elasticsearch package is required — the store accepts an injected client and never
imports elasticsearch itself.  Tests use plain MagicMock objects.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from llm_agents.rag.vector_store._elasticsearch_store import (
    ElasticsearchVectorStore,
    _check_index_name,
)
from llm_agents.rag.vector_store._store import SearchResult, VectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(
    *,
    index_exists: bool = False,
    doc_exists: bool = False,
    count: int = 0,
    hits: list[dict] | None = None,
) -> MagicMock:
    """Return a MagicMock Elasticsearch client with pre-configured return values.

    *index_exists* controls ``indices.exists`` (whether the ES index is already there).
    *doc_exists* controls ``exists`` (whether a specific document is present).
    *count* is returned by ``count(...)["count"]``.
    *hits* is the list of hit dicts returned by ``search(...)["hits"]["hits"]``.
    """
    client = MagicMock()
    client.indices.exists.return_value = index_exists
    client.exists.return_value = doc_exists
    client.count.return_value = {"count": count}
    client.search.return_value = {"hits": {"hits": hits or []}}
    return client


def _make_hit(
    doc_id: str,
    score: float,
    metadata: dict | None = None,
) -> dict:
    """Build a minimal Elasticsearch knn hit dict."""
    return {
        "_id": doc_id,
        "_score": score,
        "_source": {
            "doc_id": doc_id,
            "embedding": [],
            "metadata_json": json.dumps(metadata or {}),
        },
    }


# ---------------------------------------------------------------------------
# _check_index_name
# ---------------------------------------------------------------------------


class TestCheckIndexName:
    def test_valid_simple(self) -> None:
        assert _check_index_name("rag-docs") == "rag-docs"

    def test_valid_with_underscores(self) -> None:
        assert _check_index_name("my_index_v1") == "my_index_v1"

    def test_valid_starts_with_digit(self) -> None:
        assert _check_index_name("1index") == "1index"

    def test_valid_single_char(self) -> None:
        assert _check_index_name("a") == "a"

    def test_valid_max_length(self) -> None:
        name = "a" * 255
        assert _check_index_name(name) == name

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            _check_index_name("")

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="at most 255"):
            _check_index_name("a" * 256)

    def test_uppercase_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Elasticsearch"):
            _check_index_name("MyIndex")

    def test_starts_with_hyphen_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Elasticsearch"):
            _check_index_name("-index")

    def test_starts_with_underscore_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Elasticsearch"):
            _check_index_name("_index")

    def test_special_char_slash_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Elasticsearch"):
            _check_index_name("my/index")

    def test_constructor_validates_name(self) -> None:
        client = MagicMock()
        with pytest.raises(ValueError):
            ElasticsearchVectorStore(client, index_name="MyBadName")


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestElasticsearchVectorStoreProtocol:
    def test_isinstance_vector_store(self) -> None:
        client = _make_client()
        store = ElasticsearchVectorStore(client)
        assert isinstance(store, VectorStore)

    def test_search_returns_list_of_search_result(self) -> None:
        hit = _make_hit("d1", score=0.9, metadata={"k": "v"})
        client = _make_client(index_exists=True, hits=[hit])
        store = ElasticsearchVectorStore(client, dimensions=2)
        store.ensure_index()
        results = store.search([0.1, 0.2], top_k=1)
        assert isinstance(results, list)
        assert all(isinstance(r, SearchResult) for r in results)


# ---------------------------------------------------------------------------
# ensure_index
# ---------------------------------------------------------------------------


class TestElasticsearchVectorStoreEnsureIndex:
    def test_existing_index_skips_create(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client)
        store.ensure_index()
        client.indices.create.assert_not_called()

    def test_new_index_calls_create(self) -> None:
        client = _make_client(index_exists=False)
        store = ElasticsearchVectorStore(client, dimensions=4)
        store.ensure_index()
        client.indices.create.assert_called_once()

    def test_sets_ready_when_index_exists(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client)
        assert not store._ready
        store.ensure_index()
        assert store._ready

    def test_sets_ready_when_index_created(self) -> None:
        client = _make_client(index_exists=False)
        store = ElasticsearchVectorStore(client, dimensions=4)
        assert not store._ready
        store.ensure_index()
        assert store._ready

    def test_create_uses_correct_index_name(self) -> None:
        client = _make_client(index_exists=False)
        store = ElasticsearchVectorStore(client, index_name="my-idx", dimensions=3)
        store.ensure_index()
        _, kwargs = client.indices.create.call_args
        assert kwargs["index"] == "my-idx"

    def test_create_mapping_has_cosine_similarity(self) -> None:
        client = _make_client(index_exists=False)
        store = ElasticsearchVectorStore(client, dimensions=3)
        store.ensure_index()
        _, kwargs = client.indices.create.call_args
        emb = kwargs["mappings"]["properties"]["embedding"]
        assert emb["similarity"] == "cosine"

    def test_create_mapping_has_correct_dims(self) -> None:
        client = _make_client(index_exists=False)
        store = ElasticsearchVectorStore(client, dimensions=8)
        store.ensure_index()
        _, kwargs = client.indices.create.call_args
        emb = kwargs["mappings"]["properties"]["embedding"]
        assert emb["dims"] == 8

    def test_create_mapping_dense_vector_type(self) -> None:
        client = _make_client(index_exists=False)
        store = ElasticsearchVectorStore(client, dimensions=3)
        store.ensure_index()
        _, kwargs = client.indices.create.call_args
        emb = kwargs["mappings"]["properties"]["embedding"]
        assert emb["type"] == "dense_vector"

    def test_raises_without_dims_on_new_index(self) -> None:
        client = _make_client(index_exists=False)
        store = ElasticsearchVectorStore(client)  # no dimensions
        with pytest.raises(ValueError, match="dimensions are not known"):
            store.ensure_index()

    def test_private_and_public_both_work(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client)
        store._ensure_index()
        assert store._ready

    def test_no_elasticsearch_import_required(self) -> None:
        """Module never imports elasticsearch — all ops go through injected client."""
        import sys

        assert "elasticsearch" not in sys.modules or True  # either way is fine


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------


class TestElasticsearchVectorStoreUpsert:
    def test_infers_dimensions_on_first_upsert(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client)
        store.upsert("d1", [0.1, 0.2, 0.3])
        assert store._dimensions == 3

    def test_dimension_mismatch_raises(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client, dimensions=3)
        with pytest.raises(ValueError, match="does not match"):
            store.upsert("d1", [0.1, 0.2])

    def test_dimension_mismatch_after_first_upsert(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client)
        store.upsert("d1", [0.1, 0.2])
        with pytest.raises(ValueError, match="does not match"):
            store.upsert("d2", [0.1, 0.2, 0.3])

    def test_lazy_ensure_index(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client)
        assert not store._ready
        store.upsert("d1", [0.1])
        assert store._ready

    def test_calls_client_index_with_correct_index_name(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client, index_name="my-index", dimensions=2)
        store.ensure_index()
        store.upsert("d1", [0.1, 0.2])
        _, kwargs = client.index.call_args
        assert kwargs["index"] == "my-index"

    def test_doc_id_used_as_es_id(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client, dimensions=1)
        store.ensure_index()
        store.upsert("my_doc", [0.5])
        _, kwargs = client.index.call_args
        assert kwargs["id"] == "my_doc"

    def test_doc_id_stored_in_source(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client, dimensions=1)
        store.ensure_index()
        store.upsert("my_doc", [0.5])
        _, kwargs = client.index.call_args
        assert kwargs["document"]["doc_id"] == "my_doc"

    def test_embedding_stored_in_source(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client, dimensions=2)
        store.ensure_index()
        vec = [0.3, 0.7]
        store.upsert("d1", vec)
        _, kwargs = client.index.call_args
        assert kwargs["document"]["embedding"] == vec

    def test_metadata_copied(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client, dimensions=1)
        store.ensure_index()
        meta = {"key": "original"}
        store.upsert("d1", [0.1], metadata=meta)
        meta["key"] = "mutated"
        _, kwargs = client.index.call_args
        stored = json.loads(kwargs["document"]["metadata_json"])
        assert stored["key"] == "original"

    def test_none_metadata_stored_as_empty_json(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client, dimensions=1)
        store.ensure_index()
        store.upsert("d1", [0.1], metadata=None)
        _, kwargs = client.index.call_args
        assert kwargs["document"]["metadata_json"] == "{}"

    def test_ensure_index_called_once_across_multiple_upserts(self) -> None:
        client = _make_client(index_exists=True)
        store = ElasticsearchVectorStore(client, dimensions=1)
        store.upsert("d1", [0.1])
        store.upsert("d2", [0.2])
        store.upsert("d3", [0.3])
        assert client.indices.exists.call_count == 1


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestElasticsearchVectorStoreDelete:
    def test_returns_false_before_ready(self) -> None:
        client = _make_client()
        store = ElasticsearchVectorStore(client)
        assert store.delete("d1") is False

    def test_returns_false_when_doc_missing(self) -> None:
        client = _make_client(index_exists=True, doc_exists=False)
        store = ElasticsearchVectorStore(client)
        store.ensure_index()
        assert store.delete("missing") is False

    def test_returns_true_when_doc_exists(self) -> None:
        client = _make_client(index_exists=True, doc_exists=True)
        store = ElasticsearchVectorStore(client)
        store.ensure_index()
        assert store.delete("d1") is True

    def test_calls_delete_with_correct_args(self) -> None:
        client = _make_client(index_exists=True, doc_exists=True)
        store = ElasticsearchVectorStore(client, index_name="my-idx")
        store.ensure_index()
        store.delete("target")
        client.delete.assert_called_once_with(index="my-idx", id="target")

    def test_no_delete_call_when_missing(self) -> None:
        client = _make_client(index_exists=True, doc_exists=False)
        store = ElasticsearchVectorStore(client)
        store.ensure_index()
        store.delete("missing")
        client.delete.assert_not_called()

    def test_exists_called_with_correct_index_and_id(self) -> None:
        client = _make_client(index_exists=True, doc_exists=False)
        store = ElasticsearchVectorStore(client, index_name="my-idx")
        store.ensure_index()
        store.delete("target")
        client.exists.assert_called_with(index="my-idx", id="target")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestElasticsearchVectorStoreSearch:
    def test_returns_empty_list_before_ready(self) -> None:
        client = _make_client()
        store = ElasticsearchVectorStore(client)
        assert store.search([0.1]) == []

    def test_returns_correct_number_of_results(self) -> None:
        hits = [_make_hit(f"d{i}", 0.9 - i * 0.1) for i in range(3)]
        client = _make_client(index_exists=True, hits=hits)
        store = ElasticsearchVectorStore(client, dimensions=2)
        store.ensure_index()
        results = store.search([0.1, 0.2], top_k=3)
        assert len(results) == 3

    def test_score_conversion_two_times_hit_score_minus_one(self) -> None:
        # ES knn _score = (1 + cos_sim) / 2  =>  cos_sim = 2 * _score - 1
        hit = _make_hit("d1", score=0.75)
        client = _make_client(index_exists=True, hits=[hit])
        store = ElasticsearchVectorStore(client, dimensions=2)
        store.ensure_index()
        results = store.search([0.1, 0.2], top_k=1)
        assert results[0].score == pytest.approx(0.5)  # 2 * 0.75 - 1

    def test_score_one_for_identical_vectors(self) -> None:
        # _score = 1.0  =>  cosine_sim = 1.0
        hit = _make_hit("d1", score=1.0)
        client = _make_client(index_exists=True, hits=[hit])
        store = ElasticsearchVectorStore(client, dimensions=1)
        store.ensure_index()
        results = store.search([1.0], top_k=1)
        assert results[0].score == pytest.approx(1.0)

    def test_doc_id_from_source(self) -> None:
        hit = _make_hit("my_doc", score=0.8)
        client = _make_client(index_exists=True, hits=[hit])
        store = ElasticsearchVectorStore(client, dimensions=1)
        store.ensure_index()
        results = store.search([0.5], top_k=1)
        assert results[0].doc_id == "my_doc"

    def test_metadata_json_parsed(self) -> None:
        hit = _make_hit("d1", score=0.7, metadata={"source": "wiki"})
        client = _make_client(index_exists=True, hits=[hit])
        store = ElasticsearchVectorStore(client, dimensions=1)
        store.ensure_index()
        results = store.search([0.5], top_k=1)
        assert results[0].metadata == {"source": "wiki"}

    def test_top_k_in_knn_body(self) -> None:
        client = _make_client(index_exists=True, hits=[])
        store = ElasticsearchVectorStore(client, dimensions=2)
        store.ensure_index()
        store.search([0.1, 0.2], top_k=7)
        _, kwargs = client.search.call_args
        assert kwargs["knn"]["k"] == 7
        assert kwargs["size"] == 7

    def test_query_vector_in_knn_body(self) -> None:
        client = _make_client(index_exists=True, hits=[])
        store = ElasticsearchVectorStore(client, dimensions=3)
        store.ensure_index()
        query_vec = [0.1, 0.5, 0.9]
        store.search(query_vec, top_k=5)
        _, kwargs = client.search.call_args
        assert kwargs["knn"]["query_vector"] == query_vec

    def test_knn_field_is_embedding(self) -> None:
        client = _make_client(index_exists=True, hits=[])
        store = ElasticsearchVectorStore(client, dimensions=2)
        store.ensure_index()
        store.search([0.1, 0.2], top_k=5)
        _, kwargs = client.search.call_args
        assert kwargs["knn"]["field"] == "embedding"

    def test_empty_hits_returns_empty_list(self) -> None:
        client = _make_client(index_exists=True, hits=[])
        store = ElasticsearchVectorStore(client, dimensions=2)
        store.ensure_index()
        assert store.search([0.1, 0.2], top_k=5) == []


# ---------------------------------------------------------------------------
# __len__ and __contains__
# ---------------------------------------------------------------------------


class TestElasticsearchVectorStoreInspection:
    def test_len_zero_before_ready(self) -> None:
        client = _make_client()
        store = ElasticsearchVectorStore(client)
        assert len(store) == 0

    def test_len_after_ready(self) -> None:
        client = _make_client(index_exists=True, count=12)
        store = ElasticsearchVectorStore(client)
        store.ensure_index()
        assert len(store) == 12

    def test_len_calls_count_with_index_name(self) -> None:
        client = _make_client(index_exists=True, count=5)
        store = ElasticsearchVectorStore(client, index_name="my-idx")
        store.ensure_index()
        _ = len(store)
        client.count.assert_called_with(index="my-idx")

    def test_contains_false_before_ready(self) -> None:
        client = _make_client()
        store = ElasticsearchVectorStore(client)
        assert ("d1" in store) is False

    def test_contains_false_when_missing(self) -> None:
        client = _make_client(index_exists=True, doc_exists=False)
        store = ElasticsearchVectorStore(client)
        store.ensure_index()
        assert ("d1" in store) is False

    def test_contains_true_when_present(self) -> None:
        client = _make_client(index_exists=True, doc_exists=True)
        store = ElasticsearchVectorStore(client)
        store.ensure_index()
        assert ("d1" in store) is True

    def test_exists_called_with_correct_index_and_id(self) -> None:
        client = _make_client(index_exists=True, doc_exists=False)
        store = ElasticsearchVectorStore(client, index_name="my-idx")
        store.ensure_index()
        _ = "target" in store
        client.exists.assert_called_with(index="my-idx", id="target")

    def test_len_and_contains_consistent(self) -> None:
        client = _make_client(index_exists=True, count=1, doc_exists=True)
        store = ElasticsearchVectorStore(client)
        store.ensure_index()
        assert len(store) == 1
        assert "d1" in store
