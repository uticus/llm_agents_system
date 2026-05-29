"""Retrieval: dense passage retrieval over a vector store.

Public surface
--------------
- :class:`RetrievedPassage` — a passage returned from retrieval (doc_id, text, score, metadata).
- :class:`DenseRetriever` — embed query, search vector store, apply metadata filters.
"""

from llm_agents.rag.retrieval._retriever import DenseRetriever, RetrievedPassage

__all__ = [
    "DenseRetriever",
    "RetrievedPassage",
]
