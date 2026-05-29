"""Data ingestion: connector -> parser -> chunk -> upsert pipeline.

Orchestrates incremental document ingestion with content-hash deduplication.

Public surface
--------------
- :class:`IngestionPipeline` — fetch, parse, chunk, dedup, upsert orchestrator.
- :class:`IngestionReport` — per-run statistics (fetched, parsed, skipped, upserted).
"""

from llm_agents.data.ingestion._models import IngestionReport
from llm_agents.data.ingestion._pipeline import IngestionPipeline

__all__ = [
    "IngestionPipeline",
    "IngestionReport",
]
