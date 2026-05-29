"""Data models for the ingestion subsystem.

:class:`IngestionReport` summarises a single run of :class:`IngestionPipeline`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IngestionReport:
    """Summary of one ingestion run.

    Attributes:
        fetched:  Number of documents fetched from the connector.
        parsed:   Number of documents successfully parsed.
        skipped:  Number of documents skipped due to content-hash deduplication.
        upserted: Number of document chunks passed to the upsert callable.
    """

    fetched: int = 0
    parsed: int = 0
    skipped: int = 0
    upserted: int = 0
    errors: list[str] = field(default_factory=list)
