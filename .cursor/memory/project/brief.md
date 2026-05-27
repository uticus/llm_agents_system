# Project Brief
# File: .cursor/memory/project/brief.md

> Maintained by: Memory writer
> Purpose: stable facts about what the project is, what it does, and what it must not do.
> Agents read this to understand project identity before any task.

---

## What the project is

llm_agents_system is a Python platform for building and orchestrating LLM-based agent
systems. It provides composable subsystems spanning model management, data ingestion,
retrieval-augmented generation, agent capabilities, serving, fine-tuning, and evaluation.
Heavy/third-party integrations sit behind thin interfaces and are gated by optional
dependency extras; the default install stays light.

---

## Public API

Entry point: the `llm_agents` Python package. Subsystems are importable subpackages grouped
into layers under `src/llm_agents/`. Runtime layers: `infra/` → `data/` → `rag/` → `core/`
→ `serving/`. Offline layers: `training/`, `evaluation/` (they depend on the runtime layers;
nothing in the runtime path depends on them). Public surface is the set of classes/functions
re-exported from each subpackage `__init__.py`.

Public interfaces (stable, API-sensitive):
- `src/llm_agents/__init__.py` — top-level package exports (the seven groups)
- Each group and subsystem `__init__.py` — public surface
- The framework's interface types (`ModelBackend`, `VectorStore`, `Embedder`, `Retriever`,
  ...) — concrete backends are pluggable adapters behind these
- `src/llm_agents/config.py` — `Settings` / `load_settings()`

---

## Supported use cases

infra (runtime infrastructure):
- Model hub — load/version models across OpenAI, HuggingFace, GGUF (llama.cpp/vLLM)
- Inference routing — route requests across providers/models by policy
- Cost/latency optimization — caching, batching, model-tier selection, budget tracking
- Guardrails — output filtering and tone/compliance enforcement
- Tracing — structured spans across agent/tool/LLM calls
- Observability — metrics, logging, dashboards

data (ingestion):
- Connectors — PostgreSQL, Confluence, Jira, Google Drive
- Parsers — PDF, DOCX, custom documents
- Ingestion — continuous pull → parse → chunk → embed

rag (retrieval-augmented generation):
- Embeddings, vector store, indexing, retrieval, reranking, and the RAG pipeline

core (agent capabilities):
- Agent memory, planning, hierarchical agents, tool orchestration, long-context handling,
  prompting, replay analysis

serving:
- FastAPI services exposing orchestration, RAG, and chat

training (offline MLOps):
- Fine-tuning (Transformers + PEFT), datasets, experiment tracking (MLflow/W&B/DVC)

evaluation (offline):
- Evaluation framework (incl. BLEU/ROUGE/F1), prompt evaluation, benchmarking,
  hallucination detection

---

## Language support

| Language | Role | Location |
|---|---|---|
| Python 3.12+ | Primary | `src/llm_agents/` |

---

## Key constraints

**Light core, heavy extras**: the core depends on nothing heavy. Local inference, RAG
backends, training, serving, and data connectors are opt-in via pyproject optional extras
(`local-inference`, `rag`, `training`, `serving`, `data`, `tracking`). Code calls thin
interfaces; concrete frameworks (LangChain, Haystack, vLLM, NeMo, ...) are pluggable
adapters — never imported on the default path.

**Non-determinism**: LLM responses are inherently non-deterministic. Reproducibility is
achieved through recorded run traces (replay_analysis), not bit-identical outputs.

**Grounding over recall**: prefer grounding answers via RAG over relying on a model's
parametric memory; fine-tuning targets style/format, not fresh knowledge.

---

## What the project does NOT do

- Does not provide an end-user UI — it is a platform/library (serving exposes APIs only)
- Does not bundle heavy ML/RAG dependencies in the default install (they are optional extras)
- Does not hardcode a single LLM provider, vector store, or orchestration framework —
  everything is behind an interface

---

## Project structure (key paths)

| Path | Contents |
|---|---|
| `src/llm_agents/infra/` | Model hub, routing, cost/latency, guardrails, tracing, observability |
| `src/llm_agents/data/` | Connectors, parsers, ingestion |
| `src/llm_agents/rag/` | Embeddings, vector store, indexing, retrieval, reranking, pipeline |
| `src/llm_agents/core/` | Agent capabilities (memory, planning, tools, prompting, ...) |
| `src/llm_agents/serving/` | FastAPI serving |
| `src/llm_agents/training/` | Fine-tuning, datasets, experiment tracking (offline) |
| `src/llm_agents/evaluation/` | Evaluation, prompts, benchmarking, hallucination (offline) |
| `src/llm_agents/config.py` | Typed runtime settings |
| `tests/` | pytest suite (`unit/`, `integration/`, `fixtures/`) |
| `configs/` | Runtime + observability config |
| `deploy/` | Dockerfile, docker-compose, .dockerignore |
| `pyproject.toml` | Metadata, deps, optional extras, ruff/pytest config (uv) |
| `.cursor/` | Agents pipeline (workflow, roles, memory) |

---

## Integration test rule

Integration tests must replicate real agent usage sequences exactly. Do not reorder or
optimize the sequence of agent/tool calls — preserve the real interaction order.
