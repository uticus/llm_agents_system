"""Smoke test: the package and every subsystem subpackage import cleanly."""

import importlib

import pytest

MODULES = [
    "llm_agents",
    "llm_agents.config",
    # infra
    "llm_agents.infra.model_hub",
    "llm_agents.infra.inference_routing",
    "llm_agents.infra.cost_latency_optimization",
    "llm_agents.infra.guardrails",
    "llm_agents.infra.tracing",
    "llm_agents.infra.observability",
    # data
    "llm_agents.data.connectors",
    "llm_agents.data.parsers",
    "llm_agents.data.ingestion",
    # rag
    "llm_agents.rag.embeddings",
    "llm_agents.rag.vector_store",
    "llm_agents.rag.indexing",
    "llm_agents.rag.retrieval",
    "llm_agents.rag.reranking",
    "llm_agents.rag.pipeline",
    # core
    "llm_agents.core.agent_memory",
    "llm_agents.core.hierarchical_agents",
    "llm_agents.core.planning",
    "llm_agents.core.tool_orchestration",
    "llm_agents.core.long_context",
    "llm_agents.core.prompting",
    "llm_agents.core.replay_analysis",
    # serving
    "llm_agents.serving.api",
    # training (offline)
    "llm_agents.training.fine_tuning",
    "llm_agents.training.datasets",
    "llm_agents.training.experiment_tracking",
    # evaluation (offline)
    "llm_agents.evaluation.framework",
    "llm_agents.evaluation.prompts",
    "llm_agents.evaluation.benchmarking",
    "llm_agents.evaluation.hallucination",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    try:
        importlib.import_module(name)
    except ModuleNotFoundError as exc:
        pytest.skip(f"optional dependency not installed: {exc.name}")


def test_settings_load():
    from llm_agents.config import load_settings

    settings = load_settings()
    assert settings.environment
    assert settings.seed == 0
