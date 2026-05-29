"""Reranking: cross-encoder reranking of retrieved passages.

Public surface
--------------
- :class:`Reranker` — structural Protocol for passage rerankers.
- :class:`FakeReranker` — deterministic test reranker (reverses list, truncates).
- :class:`ScoreReranker` — sorts passages by a caller-supplied scorer callable.
"""

from llm_agents.rag.reranking._reranker import FakeReranker, Reranker, ScoreReranker

__all__ = [
    "FakeReranker",
    "Reranker",
    "ScoreReranker",
]
