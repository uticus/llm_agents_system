"""RAG pipeline: retrieve, optionally rerank, then generate grounded responses.

Public surface
--------------
- :class:`GroundedAnswer` — query, generated answer, and cited passages.
- :class:`RagPipeline` — retrieve -> (rerank) -> generate orchestrator.
"""

from llm_agents.rag.pipeline._pipeline import GroundedAnswer, RagPipeline

__all__ = [
    "GroundedAnswer",
    "RagPipeline",
]
