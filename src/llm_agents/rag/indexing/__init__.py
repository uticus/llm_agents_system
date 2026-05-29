"""Indexing: chunk -> embed -> upsert pipeline that ingests documents into a vector store.

Public surface
--------------
- :class:`Indexer` — chunk, embed, and upsert documents into a vector store.
- :class:`IndexReport` — per-run statistics (docs, chunks added/skipped).
"""

from llm_agents.rag.indexing._indexer import Indexer, IndexReport

__all__ = [
    "IndexReport",
    "Indexer",
]
