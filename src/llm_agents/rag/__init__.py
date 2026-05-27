"""Retrieval-Augmented Generation.

Index internal documents and ground LLM responses on retrieved context. Subsystems are
composed behind thin interfaces (``Embedder``, ``VectorStore``, ``Retriever``,
``Reranker``) so concrete backends (FAISS, pgvector, Weaviate, Chroma, Elasticsearch;
sentence-transformers or provider embeddings) are pluggable adapters.

Subsystems:
    embeddings     text embedding behind an Embedder interface
    vector_store   pluggable vector index behind a VectorStore interface
    indexing       chunk -> embed -> upsert pipeline
    retrieval      dense passage retrieval
    reranking      cross-encoder reranking
    pipeline       retrieve (-> rerank) -> generate grounded answers

Requires the ``rag`` extra for local embedding/index backends.
"""

__all__ = [
    "embeddings",
    "vector_store",
    "indexing",
    "retrieval",
    "reranking",
    "pipeline",
]
