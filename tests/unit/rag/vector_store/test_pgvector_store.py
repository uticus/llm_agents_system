"""Unit tests for rag/vector_store: PgVectorStore.

All tests use a MagicMock psycopg connection; no live PostgreSQL server is
required.  The ``pgvector`` Python package is mocked via ``patch.dict`` so
the tests run without installing the ``pgvector`` extra.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from llm_agents.rag.vector_store._pgvector_store import PgVectorStore, _check_identifier
from llm_agents.rag.vector_store._store import SearchResult, VectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conn(
    rows: list | None = None,
    fetchone_value: object = None,
    rowcount: int = 0,
) -> tuple[MagicMock, MagicMock]:
    """Return (conn, cursor) MagicMock pair ready for use in tests.

    Args:
        rows:           Return value of ``cursor.fetchall()``.
        fetchone_value: Return value of ``cursor.fetchone()``.
        rowcount:       Value of ``cursor.rowcount`` (used by DELETE).
    """
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = rows or []
    cursor.fetchone.return_value = fetchone_value
    cursor.rowcount = rowcount
    # wire up the context-manager protocol: `with conn.cursor() as cur:`
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def pgvector_patch():
    """Patch sys.modules so ``pgvector.psycopg`` is a no-op mock for every test."""
    mock = MagicMock()
    with patch.dict("sys.modules", {"pgvector": mock, "pgvector.psycopg": mock}):
        yield mock


# ---------------------------------------------------------------------------
# Identifier validation
# ---------------------------------------------------------------------------


class TestCheckIdentifier:
    def test_valid_simple_name(self) -> None:
        assert _check_identifier("my_table") == "my_table"

    def test_name_with_digits(self) -> None:
        assert _check_identifier("vecs_v2") == "vecs_v2"

    def test_underscore_prefix(self) -> None:
        assert _check_identifier("_private") == "_private"

    def test_digit_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _check_identifier("1bad")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _check_identifier("")

    def test_hyphen_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _check_identifier("my-table")

    def test_space_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _check_identifier("my table")

    def test_injection_attempt_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _check_identifier("t; DROP TABLE t--")

    def test_constructor_validates_table(self) -> None:
        conn, _ = _make_conn()
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            PgVectorStore(conn, table="bad-name")


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestPgVectorStoreProtocol:
    def test_satisfies_vector_store_protocol(self) -> None:
        conn, _ = _make_conn()
        assert isinstance(PgVectorStore(conn), VectorStore)

    def test_search_returns_search_result_instances(self) -> None:
        rows = [("doc1", 0.9, {"k": "v"})]
        conn, _ = _make_conn(rows=rows)
        store = PgVectorStore(conn, dimensions=2)
        store._ready = True
        results = store.search([1.0, 0.0], top_k=1)
        assert all(isinstance(r, SearchResult) for r in results)


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


class TestPgVectorStoreUpsert:
    def test_first_upsert_infers_dimensions(self) -> None:
        conn, _ = _make_conn()
        store = PgVectorStore(conn)
        store.upsert("doc", [1.0, 0.0, 0.0])
        assert store._dimensions == 3

    def test_upsert_triggers_ensure_table(self) -> None:
        conn, _ = _make_conn()
        store = PgVectorStore(conn, dimensions=3)
        assert not store._ready
        store.upsert("doc", [1.0, 0.0, 0.0])
        assert store._ready

    def test_upsert_calls_commit(self) -> None:
        conn, _ = _make_conn()
        store = PgVectorStore(conn, dimensions=3)
        store._ready = True
        store.upsert("doc", [1.0, 0.0, 0.0])
        conn.commit.assert_called()

    def test_upsert_sql_contains_insert_on_conflict(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=3)
        store._ready = True
        store.upsert("doc", [1.0, 0.0, 0.0])
        sql = cursor.execute.call_args[0][0]
        assert "INSERT INTO" in sql
        assert "ON CONFLICT" in sql

    def test_upsert_passes_doc_id_and_vector(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=2)
        store._ready = True
        store.upsert("x", [0.5, 0.5])
        params = cursor.execute.call_args[0][1]
        assert params[0] == "x"
        assert params[1] == [0.5, 0.5]

    def test_dimension_mismatch_raises(self) -> None:
        conn, _ = _make_conn()
        store = PgVectorStore(conn, dimensions=4)
        with pytest.raises(ValueError, match="dimensionality"):
            store.upsert("doc", [1.0, 0.0])

    def test_dimension_mismatch_message_includes_lengths(self) -> None:
        conn, _ = _make_conn()
        store = PgVectorStore(conn, dimensions=4)
        with pytest.raises(ValueError, match="2"):
            store.upsert("doc", [1.0, 0.0])

    def test_metadata_serialised_as_json(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=3)
        store._ready = True
        store.upsert("doc", [1.0, 0.0, 0.0], {"k": "v"})
        params = cursor.execute.call_args[0][1]
        assert json.loads(params[2]) == {"k": "v"}

    def test_no_metadata_serialises_to_empty_object(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=3)
        store._ready = True
        store.upsert("doc", [1.0, 0.0, 0.0])
        params = cursor.execute.call_args[0][1]
        assert json.loads(params[2]) == {}

    def test_metadata_is_copied_before_storage(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=3)
        store._ready = True
        meta = {"k": "original"}
        store.upsert("doc", [1.0, 0.0, 0.0], meta)
        first_params = cursor.execute.call_args[0][1]
        meta["k"] = "mutated"
        # JSON string was captured at upsert time; mutation does not change it
        assert json.loads(first_params[2])["k"] == "original"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestPgVectorStoreDelete:
    def test_delete_before_ready_returns_false(self) -> None:
        conn, _ = _make_conn()
        store = PgVectorStore(conn)
        assert store.delete("nonexistent") is False

    def test_delete_existing_returns_true(self) -> None:
        conn, _ = _make_conn(rowcount=1)
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        assert store.delete("doc") is True

    def test_delete_missing_returns_false(self) -> None:
        conn, _ = _make_conn(rowcount=0)
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        assert store.delete("nonexistent") is False

    def test_delete_calls_commit(self) -> None:
        conn, _ = _make_conn(rowcount=1)
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        store.delete("doc")
        conn.commit.assert_called()

    def test_delete_passes_doc_id_as_param(self) -> None:
        conn, cursor = _make_conn(rowcount=1)
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        store.delete("my_doc")
        params = cursor.execute.call_args[0][1]
        assert params == ("my_doc",)

    def test_delete_sql_contains_delete_from(self) -> None:
        conn, cursor = _make_conn(rowcount=0)
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        store.delete("doc")
        sql = cursor.execute.call_args[0][0]
        assert "DELETE FROM" in sql


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestPgVectorStoreSearch:
    def test_search_before_ready_returns_empty(self) -> None:
        conn, _ = _make_conn()
        store = PgVectorStore(conn)
        assert store.search([1.0, 0.0]) == []

    def test_search_returns_correct_number_of_results(self) -> None:
        rows = [("a", 0.9, {}), ("b", 0.7, {})]
        conn, _ = _make_conn(rows=rows)
        store = PgVectorStore(conn, dimensions=2)
        store._ready = True
        assert len(store.search([1.0, 0.0], top_k=5)) == 2

    def test_search_result_fields(self) -> None:
        rows = [("doc1", 0.95, {"src": "wiki"})]
        conn, _ = _make_conn(rows=rows)
        store = PgVectorStore(conn, dimensions=2)
        store._ready = True
        results = store.search([1.0, 0.0])
        assert results[0].doc_id == "doc1"
        assert results[0].score == pytest.approx(0.95)
        assert results[0].metadata == {"src": "wiki"}

    def test_search_passes_top_k_to_sql(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=2)
        store._ready = True
        store.search([1.0, 0.0], top_k=7)
        params = cursor.execute.call_args[0][1]
        assert params[-1] == 7

    def test_search_sql_uses_cosine_distance_operator(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=2)
        store._ready = True
        store.search([1.0, 0.0])
        sql = cursor.execute.call_args[0][0]
        assert "<=>" in sql

    def test_search_sql_inverts_distance_to_score(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=2)
        store._ready = True
        store.search([1.0, 0.0])
        sql = cursor.execute.call_args[0][0]
        assert "1.0 - dist" in sql

    def test_search_metadata_from_dict(self) -> None:
        rows = [("doc", 0.9, {"key": "val"})]
        conn, _ = _make_conn(rows=rows)
        store = PgVectorStore(conn, dimensions=2)
        store._ready = True
        results = store.search([1.0, 0.0])
        assert results[0].metadata == {"key": "val"}

    def test_search_metadata_from_json_string(self) -> None:
        rows = [("doc", 0.9, '{"key": "val"}')]  # string JSONB (not auto-decoded)
        conn, _ = _make_conn(rows=rows)
        store = PgVectorStore(conn, dimensions=2)
        store._ready = True
        results = store.search([1.0, 0.0])
        assert results[0].metadata == {"key": "val"}

    def test_search_empty_metadata(self) -> None:
        rows = [("doc", 0.5, {})]
        conn, _ = _make_conn(rows=rows)
        store = PgVectorStore(conn, dimensions=2)
        store._ready = True
        results = store.search([1.0, 0.0])
        assert results[0].metadata == {}

    def test_search_passes_query_vector_as_first_param(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=3)
        store._ready = True
        qv = [0.1, 0.2, 0.3]
        store.search(qv)
        params = cursor.execute.call_args[0][1]
        assert params[0] == qv


# ---------------------------------------------------------------------------
# _ensure_table
# ---------------------------------------------------------------------------


class TestPgVectorStoreEnsureTable:
    def test_calls_register_vector_with_connection(self, pgvector_patch) -> None:
        conn, _ = _make_conn()
        store = PgVectorStore(conn, dimensions=4)
        store._ensure_table()
        pgvector_patch.register_vector.assert_called_once_with(conn)

    def test_creates_extension(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=4)
        store._ensure_table()
        sqls = [str(c) for c in cursor.execute.call_args_list]
        assert any("CREATE EXTENSION" in s for s in sqls)

    def test_creates_table(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=4)
        store._ensure_table()
        sqls = [str(c) for c in cursor.execute.call_args_list]
        assert any("CREATE TABLE" in s for s in sqls)

    def test_creates_ivfflat_index(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=4)
        store._ensure_table()
        sqls = [str(c) for c in cursor.execute.call_args_list]
        assert any("ivfflat" in s for s in sqls)

    def test_creates_cosine_ops_index(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=4)
        store._ensure_table()
        sqls = [str(c) for c in cursor.execute.call_args_list]
        assert any("vector_cosine_ops" in s for s in sqls)

    def test_sets_ready_flag(self) -> None:
        conn, _ = _make_conn()
        store = PgVectorStore(conn, dimensions=4)
        assert not store._ready
        store._ensure_table()
        assert store._ready

    def test_calls_commit(self) -> None:
        conn, _ = _make_conn()
        store = PgVectorStore(conn, dimensions=4)
        store._ensure_table()
        conn.commit.assert_called()

    def test_table_name_embedded_in_sql(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, table="my_docs", dimensions=4)
        store._ensure_table()
        sqls = [str(c) for c in cursor.execute.call_args_list]
        assert any("my_docs" in s for s in sqls)

    def test_dimensions_embedded_in_create_table(self) -> None:
        conn, cursor = _make_conn()
        store = PgVectorStore(conn, dimensions=768)
        store._ensure_table()
        sqls = [str(c) for c in cursor.execute.call_args_list]
        assert any("768" in s for s in sqls)


# ---------------------------------------------------------------------------
# Inspection (__len__ and __contains__)
# ---------------------------------------------------------------------------


class TestPgVectorStoreInspection:
    def test_len_zero_when_not_ready(self) -> None:
        conn, _ = _make_conn()
        assert len(PgVectorStore(conn)) == 0

    def test_len_queries_count_star(self) -> None:
        conn, cursor = _make_conn(fetchone_value=(5,))
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        assert len(store) == 5

    def test_len_returns_zero_on_none_row(self) -> None:
        conn, cursor = _make_conn(fetchone_value=None)
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        assert len(store) == 0

    def test_len_sql_uses_count(self) -> None:
        conn, cursor = _make_conn(fetchone_value=(0,))
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        len(store)
        sql = cursor.execute.call_args[0][0]
        assert "COUNT" in sql

    def test_contains_false_when_not_ready(self) -> None:
        conn, _ = _make_conn()
        assert "x" not in PgVectorStore(conn)

    def test_contains_true_when_row_returned(self) -> None:
        conn, cursor = _make_conn(fetchone_value=(1,))
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        assert "doc" in store

    def test_contains_false_when_no_row(self) -> None:
        conn, cursor = _make_conn(fetchone_value=None)
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        assert "doc" not in store

    def test_contains_passes_doc_id_as_param(self) -> None:
        conn, cursor = _make_conn(fetchone_value=None)
        store = PgVectorStore(conn, dimensions=4)
        store._ready = True
        _ = "target_doc" in store
        params = cursor.execute.call_args[0][1]
        assert params == ("target_doc",)


# ---------------------------------------------------------------------------
# Deferred import
# ---------------------------------------------------------------------------


class TestPgVectorStoreDeferredImport:
    def test_module_importable_with_pgvector_poisoned(self) -> None:
        """Importing PgVectorStore must not trigger ``import pgvector`` at module level.

        We verify this by reloading the module while pgvector is absent from
        sys.modules.  Operations that do not call ``_ensure_table`` (search on an
        empty store, delete before ready, len before ready) must succeed without
        touching the pgvector package.
        """
        import importlib

        with patch.dict("sys.modules", {"pgvector": None, "pgvector.psycopg": None}):
            import llm_agents.rag.vector_store._pgvector_store as mod

            importlib.reload(mod)
            conn = MagicMock()
            store = mod.PgVectorStore(conn, dimensions=2)
            # None of these trigger _ensure_table
            assert store.search([1.0, 0.0]) == []
            assert store.delete("x") is False
            assert len(store) == 0
            assert "x" not in store
