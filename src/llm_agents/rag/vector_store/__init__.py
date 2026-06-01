"""Vector store: pluggable vector index behind a ``VectorStore`` interface.

Adapters for FAISS, pgvector, Weaviate, Chroma, and Elasticsearch.

Public surface
--------------
- :class:`SearchResult` — single search result (doc_id, score, metadata).
- :class:`VectorStore` — structural Protocol for vector stores.
- :class:`InMemoryVectorStore` — brute-force in-memory store with cosine similarity.
- :class:`FAISSVectorStore` — FAISS flat inner-product index (requires ``rag`` extra).
- :class:`PgVectorStore` — PostgreSQL pgvector-backed store (requires ``pgvector`` extra).
- :class:`WeaviateVectorStore` — Weaviate HNSW-backed store (requires ``weaviate`` extra).
- :class:`ChromaVectorStore` — Chroma HNSW-backed store (requires ``chroma`` extra).
- :class:`ElasticsearchVectorStore` — Elasticsearch dense_vector HNSW store (requires ``elasticsearch`` extra).
"""

from llm_agents.rag.vector_store._chroma_store import ChromaVectorStore
from llm_agents.rag.vector_store._elasticsearch_store import ElasticsearchVectorStore
from llm_agents.rag.vector_store._faiss_store import FAISSVectorStore
from llm_agents.rag.vector_store._pgvector_store import PgVectorStore
from llm_agents.rag.vector_store._store import InMemoryVectorStore, SearchResult, VectorStore
from llm_agents.rag.vector_store._weaviate_store import WeaviateVectorStore

__all__ = [
    "ChromaVectorStore",
    "ElasticsearchVectorStore",
    "FAISSVectorStore",
    "InMemoryVectorStore",
    "PgVectorStore",
    "SearchResult",
    "VectorStore",
    "WeaviateVectorStore",
]
