"""FastAPI application factory.

:func:`create_app` assembles routers and returns a configured FastAPI instance.
All heavy imports (FastAPI, Starlette) are deferred to this module so that
importing ``serving.api`` without the ``serving`` extra installed only fails
when ``create_app`` is actually called.

Dependency injection
--------------------
Sub-systems (router, RAG pipeline, guardrail chain) are injected via
``app.state``.  Route handlers read from ``request.app.state`` so they stay
unit-testable without a real event loop.

Usage::

    from llm_agents.serving.api import create_app
    from llm_agents.infra.inference_routing import InferenceRouter
    from llm_agents.rag.pipeline import RagPipeline

    app = create_app(router=my_router, rag_pipeline=my_pipeline)
"""

from __future__ import annotations

from typing import Any


def create_app(
    *,
    router: Any = None,
    rag_pipeline: Any = None,
    guardrail_chain: Any = None,
    title: str = "LLM Agents API",
    version: str = "0.1.0",
) -> Any:
    """Create and configure a FastAPI application.

    Args:
        router:          Inference router used by the ``/chat`` endpoint.
                         May be ``None`` (endpoint returns 503).
        rag_pipeline:    RAG pipeline for the ``/rag/answer`` endpoint.
                         May be ``None`` (endpoint returns 503).
        guardrail_chain: Optional guardrail chain applied to all prompts.
        title:           API title shown in the OpenAPI schema.
        version:         API version string.

    Returns:
        Configured :class:`fastapi.FastAPI` instance.

    Raises:
        ImportError: If the ``serving`` extra (FastAPI) is not installed.
    """
    try:
        import fastapi
    except ImportError as exc:
        raise ImportError(
            "FastAPI is required.  Install the 'serving' extra: "
            "pip install llm_agents_system[serving]"
        ) from exc

    from llm_agents.serving.api._routes import build_router

    app = fastapi.FastAPI(title=title, version=version)
    app.state.inference_router = router
    app.state.rag_pipeline = rag_pipeline
    app.state.guardrail_chain = guardrail_chain

    app.include_router(build_router())
    return app
