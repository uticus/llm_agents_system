"""Vector store: pluggable vector index behind a ``VectorStore`` interface.

Adapters for FAISS, pgvector, Weaviate, Chroma, and Elasticsearch (with vector plugins).

Public surface
--------------
- :class:`SearchResult` — single search result (doc_id, score, metadata).
- :class:`VectorStore` — structural Protocol for vector stores.
- :class:`InMemoryVectorStore` — brute-force in-memory store with cosine similarity.
"""

from llm_agents.rag.vector_store._store import InMemoryVectorStore, SearchResult, VectorStore

__all__ = [
    "InMemoryVectorStore",
    "SearchResult",
    "VectorStore",
]
