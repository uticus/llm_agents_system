"""Route handlers for the serving API.

Routes
------
GET  /health          — liveness check; always 200
POST /chat            — single-turn LLM completion
POST /rag/answer      — RAG retrieval + generation
"""

from __future__ import annotations

import asyncio

# FastAPI is a deferred dependency (serving extra).  This module is only ever
# imported from _app.py *after* the import-error check, so it is safe to
# import FastAPI here at module level.
from fastapi import APIRouter, HTTPException, Request

from llm_agents.serving.api._schemas import (
    ChatRequest,
    ChatResponse,
    CitationSchema,
    HealthResponse,
    RagRequest,
    RagResponse,
)


def build_router() -> APIRouter:
    """Build and return the API router.

    Returns:
        Configured :class:`fastapi.APIRouter` with all route handlers attached.
    """
    router = APIRouter()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @router.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    # ------------------------------------------------------------------
    # Chat / completion
    # ------------------------------------------------------------------

    @router.post("/chat", response_model=ChatResponse)
    async def chat(
        body: ChatRequest,
        request: Request,
    ) -> ChatResponse:
        inference_router = request.app.state.inference_router
        guardrail_chain = request.app.state.guardrail_chain

        if inference_router is None:
            raise HTTPException(
                status_code=503,
                detail="Inference router not configured.",
            )

        prompt = body.prompt

        # Apply guardrails if configured
        if guardrail_chain is not None:
            result = guardrail_chain.run(prompt)
            if not result.passed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Prompt blocked by guardrail: {result.violation_detail}",
                )
            prompt = result.text

        # Build and send request
        from llm_agents.infra.inference_routing._models import LLMRequest

        req = LLMRequest(
            model=body.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        )

        if asyncio.iscoroutinefunction(inference_router.complete):
            response = await inference_router.complete(req)
        else:
            response = inference_router.complete(req)

        return ChatResponse(
            answer=response.content,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )

    # ------------------------------------------------------------------
    # RAG answer
    # ------------------------------------------------------------------

    @router.post("/rag/answer", response_model=RagResponse)
    async def rag_answer(
        body: RagRequest,
        request: Request,
    ) -> RagResponse:
        rag_pipeline = request.app.state.rag_pipeline
        guardrail_chain = request.app.state.guardrail_chain

        if rag_pipeline is None:
            raise HTTPException(
                status_code=503,
                detail="RAG pipeline not configured.",
            )

        query = body.query

        # Apply guardrails if configured
        if guardrail_chain is not None:
            result = guardrail_chain.run(query)
            if not result.passed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Query blocked by guardrail: {result.violation_detail}",
                )
            query = result.text

        grounded = rag_pipeline.answer(
            query,
            top_k=body.top_k,
            filters=body.filters,
        )

        citations = [
            CitationSchema(
                doc_id=p.doc_id,
                text=p.text,
                score=p.score,
            )
            for p in grounded.citations
        ]

        return RagResponse(answer=grounded.answer, citations=citations)

    return router
