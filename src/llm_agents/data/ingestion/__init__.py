"""Data ingestion: connector -> parser -> chunk -> upsert pipeline.

Orchestrates incremental document ingestion with content-hash deduplication.

Public surface
--------------
- :class:`IngestionPipeline` — fetch, parse, chunk, dedup, upsert orchestrator.
- :class:`IngestionReport` — per-run statistics (fetched, parsed, skipped, upserted).
- :class:`DeduplicationStore` — protocol for pluggable dedup backends.
- :class:`InMemoryDeduplicationStore` — default in-memory dedup store.
- :class:`SQLiteDeduplicationStore` — durable SQLite-backed dedup store.
"""

from llm_agents.data.ingestion._models import IngestionReport
from llm_agents.data.ingestion._pipeline import IngestionPipeline
from llm_agents.infra.cost_latency_optimization._dedup import (
    DeduplicationStore,
    InMemoryDeduplicationStore,
    SQLiteDeduplicationStore,
)

__all__ = [
    "DeduplicationStore",
    "IngestionPipeline",
    "IngestionReport",
    "InMemoryDeduplicationStore",
    "SQLiteDeduplicationStore",
]
