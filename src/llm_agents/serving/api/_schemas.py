"""Pydantic request/response schemas for the serving API.

All schemas are defined here to keep them importable without requiring a live
FastAPI application.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Chat / completion
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request body for the ``/chat`` endpoint.

    Attributes:
        prompt:      User prompt text.
        model:       Model identifier to route to (default ``"default"``).
        max_tokens:  Maximum tokens in the response.
        temperature: Sampling temperature (0.0 = deterministic).
    """

    prompt: str = Field(..., min_length=1)
    model: str = "default"
    max_tokens: int = Field(default=256, ge=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)


class ChatResponse(BaseModel):
    """Response body for the ``/chat`` endpoint.

    Attributes:
        answer:       Generated text.
        model:        Model that produced the response.
        prompt_tokens:       Approximate input token count (0 if unavailable).
        completion_tokens:   Approximate output token count (0 if unavailable).
    """

    answer: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


# ---------------------------------------------------------------------------
# RAG answer
# ---------------------------------------------------------------------------


class RagRequest(BaseModel):
    """Request body for the ``/rag/answer`` endpoint.

    Attributes:
        query:   User question.
        top_k:   Number of passages to retrieve (default 5).
        filters: Optional metadata filters forwarded to the retriever.
    """

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1)
    filters: dict[str, str] | None = None


class CitationSchema(BaseModel):
    """A single cited passage in a RAG response."""

    doc_id: str
    text: str
    score: float


class RagResponse(BaseModel):
    """Response body for the ``/rag/answer`` endpoint.

    Attributes:
        answer:    Generated answer grounded in retrieved passages.
        citations: Passages used to produce the answer.
    """

    answer: str
    citations: list[CitationSchema]


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response body for the ``/health`` endpoint."""

    status: str = "ok"
    version: str = "0.1.0"


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Structured error body returned on 4xx/5xx responses."""

    error: str
    detail: str | None = None
