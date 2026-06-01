"""Unit tests for rag/vector_store: WeaviateVectorStore.

All tests use a MagicMock Weaviate client; no live Weaviate instance is required.
The ``weaviate`` Python package is mocked via ``patch.dict`` so the tests run
without installing the ``weaviate`` extra.
"""

from __future__ import annotations

import json
import uuid as _uuid_module
from unittest.mock import MagicMock, patch

import pytest

from llm_agents.rag.vector_store._store import SearchResult, VectorStore
from llm_agents.rag.vector_store._weaviate_store import (
    _WEAVIATE_NS,
    WeaviateVectorStore,
    _check_collection_name,
    _doc_uuid,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(collection_exists: bool = False) -> tuple[MagicMock, MagicMock]:
    """Return (client, collection) MagicMock pair.

    Args:
        collection_exists: If True, ``client.collections.exists`` returns True
                           and ``collections.get`` is the path used.
    """
    client = MagicMock()
    collection = MagicMock()
    client.collections.exists.return_value = collection_exists
    client.collections.get.return_value = collection
    client.collections.create.return_value = collection
    return client, collection


def _make_search_object(doc_id: str, distance: float, metadata: dict) -> MagicMock:
    """Build a MagicMock representing one Weaviate search result object."""
    obj = MagicMock()
    obj.properties = {"doc_id": doc_id, "metadata_json": json.dumps(metadata)}
    obj.metadata.distance = distance
    return obj


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def weaviate_patch():
    """Patch sys.modules so weaviate sub-modules are no-op mocks for every test."""
    mock = MagicMock()
    with patch.dict(
        "sys.modules",
        {
            "weaviate": mock,
            "weaviate.classes": mock,
            "weaviate.classes.config": mock,
            "weaviate.classes.query": mock,
        },
    ):
        yield mock


# ---------------------------------------------------------------------------
# Collection name validation
# ---------------------------------------------------------------------------


class TestCheckCollectionName:
    def test_valid_name_passes(self) -> None:
        assert _check_collection_name("LlmVectors") == "LlmVectors"

    def test_name_with_digits_passes(self) -> None:
        assert _check_collection_name("RagDocs2") == "RagDocs2"

    def test_name_with_underscores_passes(self) -> None:
        assert _check_collection_name("Rag_Docs") == "Rag_Docs"

    def test_lowercase_start_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Weaviate collection name"):
            _check_collection_name("llmVectors")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Weaviate collection name"):
            _check_collection_name("")

    def test_digit_start_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Weaviate collection name"):
            _check_collection_name("1Vectors")

    def test_hyphen_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Weaviate collection name"):
            _check_collection_name("Rag-Docs")

    def test_space_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Weaviate collection name"):
            _check_collection_name("Rag Docs")

    def test_injection_attempt_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid Weaviate collection name"):
            _check_collection_name("T; DROP COLLECTION T--")

    def test_constructor_validates_collection_name(self) -> None:
        client, _ = _make_client()
        with pytest.raises(ValueError, match="Invalid Weaviate collection name"):
            WeaviateVectorStore(client, collection_name="bad-name")


# ---------------------------------------------------------------------------
# Deterministic UUID helper
# ---------------------------------------------------------------------------


class TestDocUuid:
    def test_same_doc_id_gives_same_uuid(self) -> None:
        assert _doc_uuid("doc1") == _doc_uuid("doc1")

    def test_different_doc_ids_give_different_uuids(self) -> None:
        assert _doc_uuid("doc1") != _doc_uuid("doc2")

    def test_result_is_valid_uuid_string(self) -> None:
        result = _doc_uuid("test")
        parsed = _uuid_module.UUID(result)  # raises ValueError if invalid
        assert str(parsed) == result

    def test_uses_project_namespace(self) -> None:
        expected = str(_uuid_module.uuid5(_WEAVIATE_NS, "hello"))
        assert _doc_uuid("hello") == expected


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestWeaviateVectorStoreProtocol:
    def test_satisfies_vector_store_protocol(self) -> None:
        client, _ = _make_client()
        assert isinstance(WeaviateVectorStore(client), VectorStore)

    def test_search_returns_search_result_instances(self) -> None:
        client, collection = _make_client()
        obj = _make_search_object("doc1", 0.1, {})
        collection.query.near_vector.return_value.objects = [obj]

        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        results = store.search([1.0, 0.0])
        assert all(isinstance(r, SearchResult) for r in results)


# ---------------------------------------------------------------------------
# _ensure_collection
# ---------------------------------------------------------------------------


class TestWeaviateVectorStoreEnsureCollection:
    def test_checks_collection_existence(self) -> None:
        client, _ = _make_client(collection_exists=False)
        store = WeaviateVectorStore(client, collection_name="Docs")
        store._ensure_collection()
        client.collections.exists.assert_called_once_with("Docs")

    def test_gets_existing_collection(self) -> None:
        client, collection = _make_client(collection_exists=True)
        store = WeaviateVectorStore(client, collection_name="Docs")
        store._ensure_collection()
        client.collections.get.assert_called_once_with("Docs")
        client.collections.create.assert_not_called()

    def test_creates_new_collection_when_absent(self) -> None:
        client, _ = _make_client(collection_exists=False)
        store = WeaviateVectorStore(client, collection_name="Docs")
        store._ensure_collection()
        client.collections.create.assert_called_once()
        client.collections.get.assert_not_called()

    def test_create_called_with_collection_name(self) -> None:
        client, _ = _make_client(collection_exists=False)
        store = WeaviateVectorStore(client, collection_name="MyDocs")
        store._ensure_collection()
        kwargs = client.collections.create.call_args.kwargs
        assert kwargs.get("name") == "MyDocs"

    def test_sets_ready_flag(self) -> None:
        client, _ = _make_client()
        store = WeaviateVectorStore(client)
        assert not store._ready
        store._ensure_collection()
        assert store._ready

    def test_assigns_collection_attribute(self) -> None:
        client, collection = _make_client(collection_exists=True)
        store = WeaviateVectorStore(client)
        store._ensure_collection()
        assert store._collection is collection

    def test_public_ensure_collection_delegates(self) -> None:
        client, _ = _make_client()
        store = WeaviateVectorStore(client, collection_name="X")
        store.ensure_collection()
        assert store._ready


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


class TestWeaviateVectorStoreUpsert:
    def test_first_upsert_infers_dimensions(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client)
        store.upsert("doc", [1.0, 0.0, 0.0])
        assert store._dimensions == 3

    def test_upsert_triggers_ensure_collection(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        assert not store._ready
        store.upsert("doc", [1.0, 0.0])
        assert store._ready

    def test_new_doc_calls_insert(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.upsert("doc", [1.0, 0.0])
        collection.data.insert.assert_called_once()
        collection.data.replace.assert_not_called()

    def test_existing_doc_calls_replace(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = MagicMock()  # exists
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.upsert("doc", [1.0, 0.0])
        collection.data.replace.assert_called_once()
        collection.data.insert.assert_not_called()

    def test_insert_called_with_deterministic_uuid(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.upsert("my_doc", [1.0, 0.0])
        kwargs = collection.data.insert.call_args.kwargs
        assert kwargs["uuid"] == _doc_uuid("my_doc")

    def test_replace_called_with_deterministic_uuid(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = MagicMock()
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.upsert("my_doc", [1.0, 0.0])
        kwargs = collection.data.replace.call_args.kwargs
        assert kwargs["uuid"] == _doc_uuid("my_doc")

    def test_metadata_serialised_as_json_in_props(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.upsert("doc", [1.0, 0.0], {"k": "v"})
        kwargs = collection.data.insert.call_args.kwargs
        assert json.loads(kwargs["properties"]["metadata_json"]) == {"k": "v"}

    def test_no_metadata_serialises_to_empty_object(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.upsert("doc", [1.0, 0.0])
        kwargs = collection.data.insert.call_args.kwargs
        assert json.loads(kwargs["properties"]["metadata_json"]) == {}

    def test_metadata_is_copied_before_storage(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        meta = {"k": "original"}
        store.upsert("doc", [1.0, 0.0], meta)
        first_kwargs = collection.data.insert.call_args.kwargs
        meta["k"] = "mutated"
        assert json.loads(first_kwargs["properties"]["metadata_json"])["k"] == "original"

    def test_dimension_mismatch_raises(self) -> None:
        client, _ = _make_client()
        store = WeaviateVectorStore(client, dimensions=4)
        with pytest.raises(ValueError, match="dimensionality"):
            store.upsert("doc", [1.0, 0.0])

    def test_doc_id_stored_in_properties(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.upsert("my_doc", [1.0, 0.0])
        kwargs = collection.data.insert.call_args.kwargs
        assert kwargs["properties"]["doc_id"] == "my_doc"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestWeaviateVectorStoreDelete:
    def test_delete_before_ready_returns_false(self) -> None:
        client, _ = _make_client()
        store = WeaviateVectorStore(client)
        assert store.delete("nonexistent") is False

    def test_delete_existing_returns_true(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = MagicMock()
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        assert store.delete("doc") is True

    def test_delete_missing_returns_false(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        assert store.delete("nonexistent") is False

    def test_delete_calls_delete_by_id_with_correct_uuid(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = MagicMock()
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.delete("my_doc")
        collection.data.delete_by_id.assert_called_once_with(_doc_uuid("my_doc"))

    def test_delete_missing_does_not_call_delete_by_id(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.delete("missing")
        collection.data.delete_by_id.assert_not_called()

    def test_fetch_object_by_id_receives_deterministic_uuid(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.delete("my_doc")
        collection.query.fetch_object_by_id.assert_called_once_with(_doc_uuid("my_doc"))


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestWeaviateVectorStoreSearch:
    def test_search_before_ready_returns_empty(self) -> None:
        client, _ = _make_client()
        store = WeaviateVectorStore(client)
        assert store.search([1.0, 0.0]) == []

    def test_search_returns_correct_number_of_results(self) -> None:
        client, collection = _make_client()
        objs = [_make_search_object(f"doc{i}", 0.1 * i, {}) for i in range(3)]
        collection.query.near_vector.return_value.objects = objs
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        results = store.search([1.0, 0.0], top_k=3)
        assert len(results) == 3

    def test_search_result_doc_id(self) -> None:
        client, collection = _make_client()
        collection.query.near_vector.return_value.objects = [
            _make_search_object("target_doc", 0.05, {})
        ]
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        results = store.search([1.0, 0.0])
        assert results[0].doc_id == "target_doc"

    def test_search_score_is_one_minus_distance(self) -> None:
        client, collection = _make_client()
        collection.query.near_vector.return_value.objects = [
            _make_search_object("doc", 0.2, {})
        ]
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        results = store.search([1.0, 0.0])
        assert results[0].score == pytest.approx(0.8)

    def test_search_identical_vector_score_near_one(self) -> None:
        client, collection = _make_client()
        collection.query.near_vector.return_value.objects = [
            _make_search_object("doc", 0.0, {})  # distance 0 → score 1.0
        ]
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        results = store.search([1.0, 0.0])
        assert results[0].score == pytest.approx(1.0)

    def test_search_orthogonal_vector_score_near_zero(self) -> None:
        client, collection = _make_client()
        collection.query.near_vector.return_value.objects = [
            _make_search_object("doc", 1.0, {})  # distance 1 → score 0.0
        ]
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        results = store.search([1.0, 0.0])
        assert results[0].score == pytest.approx(0.0)

    def test_search_metadata_deserialised(self) -> None:
        client, collection = _make_client()
        collection.query.near_vector.return_value.objects = [
            _make_search_object("doc", 0.1, {"src": "wiki", "page": 7})
        ]
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        results = store.search([1.0, 0.0])
        assert results[0].metadata == {"src": "wiki", "page": 7}

    def test_search_passes_top_k_as_limit(self) -> None:
        client, collection = _make_client()
        collection.query.near_vector.return_value.objects = []
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        store.search([1.0, 0.0], top_k=9)
        kwargs = collection.query.near_vector.call_args.kwargs
        assert kwargs.get("limit") == 9

    def test_search_passes_query_vector(self) -> None:
        client, collection = _make_client()
        collection.query.near_vector.return_value.objects = []
        store = WeaviateVectorStore(client, dimensions=3)
        store._ready = True
        store._collection = collection
        qv = [0.1, 0.2, 0.3]
        store.search(qv)
        kwargs = collection.query.near_vector.call_args.kwargs
        assert kwargs.get("near_vector") == qv

    def test_search_empty_collection_returns_empty_list(self) -> None:
        client, collection = _make_client()
        collection.query.near_vector.return_value.objects = []
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        assert store.search([1.0, 0.0]) == []


# ---------------------------------------------------------------------------
# Inspection (__len__ and __contains__)
# ---------------------------------------------------------------------------


class TestWeaviateVectorStoreInspection:
    def test_len_before_ready_is_zero(self) -> None:
        client, _ = _make_client()
        assert len(WeaviateVectorStore(client)) == 0

    def test_len_returns_total_count(self) -> None:
        client, collection = _make_client()
        collection.aggregate.over_all.return_value.total_count = 7
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        assert len(store) == 7

    def test_len_returns_zero_when_total_count_is_none(self) -> None:
        client, collection = _make_client()
        collection.aggregate.over_all.return_value.total_count = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        assert len(store) == 0

    def test_len_calls_over_all_with_total_count_flag(self) -> None:
        client, collection = _make_client()
        collection.aggregate.over_all.return_value.total_count = 0
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        len(store)
        collection.aggregate.over_all.assert_called_once_with(total_count=True)

    def test_contains_before_ready_is_false(self) -> None:
        client, _ = _make_client()
        assert "x" not in WeaviateVectorStore(client)

    def test_contains_true_when_object_found(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = MagicMock()
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        assert "doc" in store

    def test_contains_false_when_object_not_found(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        assert "doc" not in store

    def test_contains_uses_deterministic_uuid(self) -> None:
        client, collection = _make_client()
        collection.query.fetch_object_by_id.return_value = None
        store = WeaviateVectorStore(client, dimensions=2)
        store._ready = True
        store._collection = collection
        _ = "target" in store
        collection.query.fetch_object_by_id.assert_called_once_with(_doc_uuid("target"))


# ---------------------------------------------------------------------------
# Deferred import
# ---------------------------------------------------------------------------


class TestWeaviateVectorStoreDeferredImport:
    def test_module_importable_with_weaviate_poisoned(self) -> None:
        """Importing WeaviateVectorStore must not trigger ``import weaviate`` at module level.

        We verify by reloading the module with weaviate absent from sys.modules.
        Operations that do not call ``_ensure_collection`` or ``search`` must
        succeed without touching the weaviate package.
        """
        import importlib

        with patch.dict(
            "sys.modules",
            {
                "weaviate": None,
                "weaviate.classes": None,
                "weaviate.classes.config": None,
                "weaviate.classes.query": None,
            },
        ):
            import llm_agents.rag.vector_store._weaviate_store as mod

            importlib.reload(mod)
            client = MagicMock()
            store = mod.WeaviateVectorStore(client, dimensions=2)
            # _ready is False; these return early without importing weaviate
            assert store.search([1.0, 0.0]) == []
            assert store.delete("x") is False
            assert len(store) == 0
            assert "x" not in store
