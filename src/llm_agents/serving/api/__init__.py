"""Serving API: FastAPI services exposing orchestration, RAG, and chat endpoints.

Requires the ``serving`` extra.

Public surface
--------------
- :func:`create_app` — assemble and return a configured FastAPI application.
- :class:`ChatRequest` / :class:`ChatResponse` — chat endpoint schemas.
- :class:`RagRequest` / :class:`RagResponse` — RAG answer endpoint schemas.
- :class:`HealthResponse` — health endpoint schema.
"""

from llm_agents.serving.api._app import create_app
from llm_agents.serving.api._schemas import (
    ChatRequest,
    ChatResponse,
    CitationSchema,
    HealthResponse,
    RagRequest,
    RagResponse,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "CitationSchema",
    "HealthResponse",
    "RagRequest",
    "RagResponse",
    "create_app",
]
