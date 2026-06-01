"""Embeddings: text embedding via sentence-transformers or provider embeddings.

Behind an ``Embedder`` interface.  Local models require the ``rag`` extra;
provider adapters require the corresponding extra (``openai``, ``cohere``).

Public surface
--------------
- :class:`Embedder` — structural Protocol for text embedding models.
- :class:`FakeEmbedder` — deterministic test embedder (unit vectors).
- :class:`BatchEmbedder` — wraps any Embedder and batches calls.
- :class:`SentenceTransformerEmbedder` — local inference via sentence-transformers (``rag`` extra).
- :class:`OpenAIEmbedder` — OpenAI embeddings API via injected client (``openai`` extra).
- :class:`CohereEmbedder` — Cohere embeddings API via injected client (``cohere`` extra).
"""

from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder
from llm_agents.rag.embeddings._embedder import BatchEmbedder, Embedder, FakeEmbedder
from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder
from llm_agents.rag.embeddings._sentence_transformer_embedder import (
    SentenceTransformerEmbedder,
)

__all__ = [
    "BatchEmbedder",
    "CohereEmbedder",
    "Embedder",
    "FakeEmbedder",
    "OpenAIEmbedder",
    "SentenceTransformerEmbedder",
]
