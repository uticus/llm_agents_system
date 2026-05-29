"""IngestionPipeline: connector -> parser -> chunker -> dedup -> upsert.

Content-hash deduplication uses MD5 over the raw document content.  Chunks
whose parent document was seen in a previous run are skipped without calling
the upsert callable.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from llm_agents.data.ingestion._models import IngestionReport
from llm_agents.data.parsers._models import ParsedDocument


def _md5(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


class IngestionPipeline:
    """Orchestrates the fetch -> parse -> chunk -> dedup -> upsert flow.

    Args:
        connector: Any object satisfying the :class:`~llm_agents.data.connectors.Connector`
                   protocol.
        parser:    Any object satisfying the :class:`~llm_agents.data.parsers.DocumentParser`
                   protocol.
        chunker:   Callable ``(parsed: ParsedDocument) -> list[Any]``.
                   Returns a list of chunks (strings or arbitrary objects).
                   May return an empty list to skip a document.
        upsert:    Callable ``(chunk: Any) -> None``.
                   Called once for each non-deduplicated chunk.

    Attributes:
        _seen_hashes: Set of MD5 hashes of document contents seen in previous
                      or current runs.  Persists across multiple calls to
                      :meth:`ingest` on the same pipeline instance.
    """

    def __init__(
        self,
        connector: Any,
        parser: Any,
        chunker: Callable[[ParsedDocument], list[Any]],
        upsert: Callable[[Any], None],
    ) -> None:
        self._connector = connector
        self._parser = parser
        self._chunker = chunker
        self._upsert = upsert
        self._seen_hashes: set[str] = set()

    async def ingest(self, since_cursor: Any = None) -> IngestionReport:
        """Run one ingestion pass.

        Fetches documents from the connector (optionally filtered by
        *since_cursor*), parses each one, chunks, deduplicates via MD5 of the
        raw document content, and calls the upsert callable for each new chunk.

        Args:
            since_cursor: Passed directly to the connector's ``fetch`` method.
                          ``None`` means fetch all documents.

        Returns:
            :class:`IngestionReport` with counts for this run.
        """
        report = IngestionReport()

        async for doc in self._connector.fetch(since_cursor):
            report.fetched += 1
            content_hash = _md5(doc.content)

            if content_hash in self._seen_hashes:
                report.skipped += 1
                continue

            # Parse
            try:
                parsed = self._parser.parse(
                    doc.content,
                    metadata=doc.metadata,
                    doc_id=doc.doc_id,
                )
            except Exception as exc:  # noqa: BLE001
                report.errors.append(f"{doc.doc_id}: parse error — {exc}")
                continue

            report.parsed += 1
            self._seen_hashes.add(content_hash)

            # Chunk
            chunks = self._chunker(parsed)

            # Upsert each chunk
            for chunk in chunks:
                self._upsert(chunk)
                report.upserted += 1

        return report

    @property
    def seen_count(self) -> int:
        """Number of unique content hashes accumulated so far."""
        return len(self._seen_hashes)

    def reset_dedup(self) -> None:
        """Clear the deduplication hash set (start fresh next run)."""
        self._seen_hashes.clear()
