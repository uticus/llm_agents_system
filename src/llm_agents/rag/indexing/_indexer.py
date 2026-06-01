"""Indexer: chunk -> embed -> upsert into a VectorStore.

The indexer assigns stable, deterministic chunk IDs derived from the parent
``doc_id`` and the chunk's position, so that re-indexing the same document is
idempotent (the vector store simply overwrites existing entries with the same
IDs).

Chunk-content deduplication is managed by a
:class:`~llm_agents.infra.cost_latency_optimization.DeduplicationStore`.
The default store is
:class:`~llm_agents.infra.cost_latency_optimization.InMemoryDeduplicationStore`
(in-process; lost on restart).  Pass a
:class:`~llm_agents.infra.cost_latency_optimization.SQLiteDeduplicationStore` to persist
hashes across process restarts.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from llm_agents.infra.cost_latency_optimization._dedup import (
    DeduplicationStore,
    InMemoryDeduplicationStore,
)


def _chunk_id(doc_id: str, index: int) -> str:
    """Return a stable chunk ID: ``<doc_id>#<index>``."""
    return f"{doc_id}#{index}"


def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class IndexReport:
    """Summary of one indexing run.

    Attributes:
        docs_indexed: Number of documents processed.
        chunks_added: Number of chunks upserted into the vector store.
        chunks_skipped: Number of chunks skipped because their content
                        hash was already seen (idempotent re-index).
    """

    docs_indexed: int = 0
    chunks_added: int = 0
    chunks_skipped: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------


class Indexer:
    """Chunk -> embed -> upsert pipeline feeding a vector store.

    Chunk IDs are computed as ``"<doc_id>#<chunk_index>"`` so that re-indexing
    the same document always produces the same IDs — the vector store then
    performs an idempotent update.

    Content hashes are maintained across calls so repeated indexing of the
    same chunk content is detected and skipped without calling the embedder.

    Args:
        embedder:     Any object satisfying the :class:`~llm_agents.rag.embeddings.Embedder`
                      protocol.
        vector_store: Any object satisfying the :class:`~llm_agents.rag.vector_store.VectorStore`
                      protocol.
        chunker:      Callable ``(text: str) -> list[str]``.  Takes the
                      document text and returns a list of chunk strings.
                      Defaults to a single-chunk (identity) chunker.
        dedup_store:  Optional ``DeduplicationStore`` for tracking seen
                      chunk-content hashes.  Defaults to
                      ``InMemoryDeduplicationStore`` (state lost on restart).
                      Pass ``SQLiteDeduplicationStore`` to persist hashes
                      across process restarts.
    """

    def __init__(
        self,
        embedder: Any,
        vector_store: Any,
        chunker: Any = None,
        *,
        dedup_store: DeduplicationStore | None = None,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._chunker = chunker or (lambda text: [text])
        self._dedup_store: DeduplicationStore = (
            dedup_store if dedup_store is not None else InMemoryDeduplicationStore()
        )

    def index(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> IndexReport:
        """Index a single document.

        Chunks *text*, embeds new chunks in one batch call, and upserts each
        chunk into the vector store.

        Args:
            doc_id:   Identifier for the document.
            text:     Full text to chunk and embed.
            metadata: Optional metadata attached to every chunk entry.

        Returns:
            :class:`IndexReport` for this document.
        """
        report = IndexReport(docs_indexed=1)
        chunks: list[str] = self._chunker(text)
        meta = dict(metadata) if metadata else {}

        # Filter chunks that haven't changed since last index.
        # Store (idx, text, hash) so the hash is computed exactly once per chunk.
        new_chunks: list[tuple[int, str, str]] = []
        for idx, chunk in enumerate(chunks):
            h = _content_hash(chunk)
            if h in self._dedup_store:
                report.chunks_skipped += 1
            else:
                new_chunks.append((idx, chunk, h))

        if not new_chunks:
            return report

        # Embed all new chunks in a single batch call
        texts = [c for _, c, _ in new_chunks]
        try:
            vectors = self._embedder.embed(texts)
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"{doc_id}: embed error — {exc}")
            return report

        for (idx, _chunk, h), vector in zip(new_chunks, vectors, strict=False):
            chunk_id = _chunk_id(doc_id, idx)
            chunk_meta = {**meta, "doc_id": doc_id, "chunk_index": idx}
            self._vector_store.upsert(chunk_id, vector, metadata=chunk_meta)
            self._dedup_store.add(h)
            report.chunks_added += 1

        return report

    def index_batch(
        self,
        documents: list[tuple[str, str]],
        metadata: dict[str, Any] | None = None,
    ) -> IndexReport:
        """Index multiple documents, returning aggregated counts.

        Args:
            documents: List of ``(doc_id, text)`` tuples.
            metadata:  Optional metadata applied to every chunk.

        Returns:
            :class:`IndexReport` summing across all documents.
        """
        total = IndexReport()
        for doc_id, text in documents:
            r = self.index(doc_id, text, metadata=metadata)
            total.docs_indexed += r.docs_indexed
            total.chunks_added += r.chunks_added
            total.chunks_skipped += r.chunks_skipped
            total.errors.extend(r.errors)
        return total

    @property
    def seen_count(self) -> int:
        """Number of unique chunk-content hashes accumulated."""
        return len(self._dedup_store)

    def reset_dedup(self) -> None:
        """Clear the deduplication store."""
        self._dedup_store.reset()
