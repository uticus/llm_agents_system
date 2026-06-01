"""Indexing: chunk -> embed -> upsert pipeline that ingests documents into a vector store.

Public surface
--------------
- :class:`Indexer` — chunk, embed, and upsert documents into a vector store.
- :class:`IndexReport` — per-run statistics (docs, chunks added/skipped).
- :class:`DeduplicationStore` — protocol for pluggable dedup backends.
- :class:`InMemoryDeduplicationStore` — default in-memory dedup store.
- :class:`SQLiteDeduplicationStore` — durable SQLite-backed dedup store.
"""

from llm_agents.infra.cost_latency_optimization._dedup import (
    DeduplicationStore,
    InMemoryDeduplicationStore,
    SQLiteDeduplicationStore,
)
from llm_agents.rag.indexing._indexer import Indexer, IndexReport

__all__ = [
    "DeduplicationStore",
    "IndexReport",
    "Indexer",
    "InMemoryDeduplicationStore",
    "SQLiteDeduplicationStore",
]
