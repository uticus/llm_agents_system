"""llm_agents: a platform for building and orchestrating LLM-based agent systems.

The package is organized into layers. Runtime layers (lowest to highest):

    infra        runtime infrastructure (model hub, routing, tracing, guardrails, ...)
    data         document ingestion (connectors, parsers, ingestion)
    rag          retrieval-augmented generation (embeddings, vector store, retrieval, ...)
    core         agent capabilities (memory, planning, tools, prompting, hierarchy, ...)
    serving      HTTP serving (FastAPI APIs)

Offline layers depend on the runtime layers, but nothing in the runtime path depends on
them:

    training     fine-tuning, datasets, experiment tracking (MLOps)
    evaluation   evaluation, prompts, benchmarking, hallucination detection

Heavy/optional integrations (local inference, RAG backends, training, serving, data
connectors) live behind thin interfaces and are gated by pyproject optional extras, so the
default install stays light. See README.md.
"""

__all__ = [
    "infra",
    "data",
    "rag",
    "core",
    "serving",
    "training",
    "evaluation",
]
