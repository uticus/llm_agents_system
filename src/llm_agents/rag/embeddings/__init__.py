"""Embeddings: text embedding via sentence-transformers or provider embeddings.

Behind an ``Embedder`` interface. Local models require the ``rag`` extra.

Public surface
--------------
- :class:`Embedder` — structural Protocol for text embedding models.
- :class:`FakeEmbedder` — deterministic test embedder (unit vectors).
- :class:`BatchEmbedder` — wraps any Embedder and batches calls.
"""

from llm_agents.rag.embeddings._embedder import BatchEmbedder, Embedder, FakeEmbedder

__all__ = [
    "BatchEmbedder",
    "Embedder",
    "FakeEmbedder",
]
