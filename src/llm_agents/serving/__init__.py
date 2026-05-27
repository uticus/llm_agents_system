"""Serving.

Expose orchestration, RAG, and chat capabilities over HTTP.

Subsystems:
    api   FastAPI services and endpoints

Top of the runtime stack: depends on core, rag, and infra. Requires the ``serving`` extra.
"""

__all__ = [
    "api",
]
