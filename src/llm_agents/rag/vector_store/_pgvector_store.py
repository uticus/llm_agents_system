"""PgVectorStore — PostgreSQL pgvector-backed implementation of the VectorStore Protocol.

Uses the ``pgvector`` PostgreSQL extension and the ``pgvector`` Python package
(``pgvector.psycopg`` adapter for psycopg 3) to store and query dense vectors.

Similarity metric: cosine similarity via the ``<=>`` cosine-distance operator.
Returned score = ``1.0 − cosine_distance``, so 1.0 = identical, 0.0 = orthogonal,
and −1.0 = opposite directions.

The caller is responsible for providing an open ``psycopg.Connection``; the
store does **not** manage connection lifecycle.  Table and extension creation
happen lazily on the first :meth:`upsert` call.

``import pgvector.psycopg`` is **deferred** to the first ``_ensure_table`` call
so that importing this module without the ``pgvector`` extra installed does not
raise an ``ImportError``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from llm_agents.rag.vector_store._store import SearchResult

# ---------------------------------------------------------------------------
# Identifier validation
# ---------------------------------------------------------------------------

_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def _check_identifier(name: str) -> str:
    """Validate a table or index name; raise :class:`ValueError` on unsafe values.

    Args:
        name: Candidate SQL identifier.

    Returns:
        The identifier unchanged when it passes validation.

    Raises:
        ValueError: If ``name`` contains characters that could enable SQL injection.
    """
    if not _SAFE_IDENT.match(name):
        raise ValueError(
            f"Unsafe SQL identifier {name!r}. "
            "Use only ASCII letters, digits, and underscores (max 63 chars, "
            "starting with a letter or underscore)."
        )
    return name


# ---------------------------------------------------------------------------
# PgVectorStore
# ---------------------------------------------------------------------------


class PgVectorStore:
    """PostgreSQL pgvector-backed vector store using cosine similarity.

    The store writes vectors into a single PostgreSQL table and performs
    approximate nearest-neighbour search via the pgvector ``<=>``
    (cosine distance) operator.

    Table schema::

        CREATE TABLE <table> (
            doc_id    TEXT  PRIMARY KEY,
            embedding vector(<dimensions>) NOT NULL,
            metadata  JSONB NOT NULL DEFAULT '{}'::jsonb
        );

    An IVFFlat index on ``embedding`` (``vector_cosine_ops``) is created
    alongside the table for approximate search.

    Args:
        connection:  An open ``psycopg.Connection`` (or any object with a
                     compatible ``cursor()`` context-manager and ``commit()``).
                     The store does not close or reopen the connection.
        table:       Name of the PostgreSQL table to use.  Must be a safe SQL
                     identifier: ASCII letters, digits, and underscores, starting
                     with a letter or underscore, max 63 chars.
        dimensions:  Embedding dimensionality.  If *None* (default), the value
                     is inferred from the first :meth:`upsert` call.  All
                     subsequent upsert calls must supply the same length.

    Raises:
        ValueError: At construction time if *table* is not a safe identifier.

    Example::

        import psycopg
        from pgvector.psycopg import register_vector

        conn = psycopg.connect("postgresql://localhost/mydb")
        store = PgVectorStore(conn, table="docs", dimensions=1536)
        store.upsert("doc1", embedding, {"source": "wiki"})
        results = store.search(query_vec, top_k=5)
    """

    def __init__(
        self,
        connection: Any,
        table: str = "llm_vectors",
        dimensions: int | None = None,
    ) -> None:
        self._conn = connection
        self._table = _check_identifier(table)
        self._dimensions: int | None = dimensions
        self._ready: bool = False

    # ------------------------------------------------------------------
    # Table setup (deferred)
    # ------------------------------------------------------------------

    def _ensure_table(self) -> None:
        """Create the pgvector extension, table, and IVFFlat index if absent.

        Called lazily by :meth:`upsert` the first time a vector is written.
        Imports ``pgvector.psycopg`` at call time so the module is safe to
        import without the ``pgvector`` extra installed.
        """
        from pgvector.psycopg import register_vector  # noqa: PLC0415

        register_vector(self._conn)
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {self._table} ("
                "  doc_id    TEXT  PRIMARY KEY,"
                f" embedding vector({self._dimensions})  NOT NULL,"
                "  metadata  JSONB NOT NULL DEFAULT '{}'::jsonb"
                ")"
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {self._table}_emb_idx"
                f" ON {self._table}"
                " USING ivfflat (embedding vector_cosine_ops)"
                " WITH (lists = 100)"
            )
        self._conn.commit()
        self._ready = True

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def upsert(
        self,
        doc_id: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or update the vector for *doc_id*.

        On the first call, the table and pgvector extension are created if
        they do not yet exist (see :meth:`_ensure_table`).

        Args:
            doc_id:   Unique document identifier.
            vector:   Embedding vector.  Length must match the established
                      dimensionality of this store.
            metadata: Optional key-value metadata stored as JSONB alongside
                      the vector.  The dict is copied; caller mutations after
                      this call do not affect stored state.

        Raises:
            ValueError: If *vector* length does not match the store's
                        established dimensionality.
        """
        if self._dimensions is None:
            self._dimensions = len(vector)
        elif len(vector) != self._dimensions:
            raise ValueError(
                f"Vector length {len(vector)} does not match "
                f"store dimensionality {self._dimensions}."
            )
        if not self._ready:
            self._ensure_table()
        with self._conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self._table} (doc_id, embedding, metadata)"
                " VALUES (%s, %s, %s)"
                " ON CONFLICT (doc_id) DO UPDATE"
                "   SET embedding = EXCLUDED.embedding,"
                "       metadata  = EXCLUDED.metadata",
                (doc_id, vector, json.dumps(dict(metadata) if metadata else {})),
            )
        self._conn.commit()

    def delete(self, doc_id: str) -> bool:
        """Remove the entry for *doc_id*.

        Returns:
            ``True`` if the entry existed and was removed; ``False`` otherwise.
            Always returns ``False`` before the first :meth:`upsert` call
            (table has not yet been created).
        """
        if not self._ready:
            return False
        with self._conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {self._table} WHERE doc_id = %s",
                (doc_id,),
            )
            deleted = cur.rowcount > 0
        self._conn.commit()
        return deleted

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Return the *top_k* entries with the highest cosine similarity.

        Score is computed as ``1.0 − cosine_distance`` so that 1.0 means
        identical direction and 0.0 means orthogonal vectors.

        Returns an empty list if :meth:`upsert` has never been called (the
        table does not yet exist).

        Args:
            query_vector: Query embedding vector.
            top_k:        Maximum number of results to return.

        Returns:
            List of :class:`SearchResult` sorted by descending score.
        """
        if not self._ready:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT doc_id, 1.0 - dist AS score, metadata"
                f" FROM ("
                f"   SELECT doc_id, metadata,"
                f"          embedding <=> %s::vector AS dist"
                f"   FROM {self._table}"
                f"   ORDER BY dist"
                f"   LIMIT %s"
                f" ) sub",
                (query_vector, top_k),
            )
            rows = cur.fetchall()
        return [
            SearchResult(
                doc_id=row[0],
                score=float(row[1]),
                metadata=dict(row[2]) if isinstance(row[2], dict) else json.loads(row[2]),
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of stored vectors.

        Issues a ``SELECT COUNT(*)`` query.  Returns 0 before the first
        :meth:`upsert` call.
        """
        if not self._ready:
            return 0
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {self._table}")
            row = cur.fetchone()
        return int(row[0]) if row else 0

    def __contains__(self, doc_id: str) -> bool:
        """Return ``True`` if *doc_id* is present in the store."""
        if not self._ready:
            return False
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {self._table} WHERE doc_id = %s LIMIT 1",
                (doc_id,),
            )
            return cur.fetchone() is not None
