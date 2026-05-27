# Project Build
# File: .cursor/memory/project/build.md
# Maintained by: Memory writer + Environment agent

> Used by: Environment, Implementer, Tester
> Purpose: facts about the build system, project layout, and toolchain.
> Update when: dependencies change, layout changes, toolchain changes.

---

## Project structure

```
llm_agents_system/
  src/
    llm_agents/                     primary package
      infra/                        runtime infrastructure
        model_hub/  inference_routing/  cost_latency_optimization/
        guardrails/  tracing/  observability/
      data/                         ingestion
        connectors/  parsers/  ingestion/
      rag/                          retrieval-augmented generation
        embeddings/  vector_store/  indexing/  retrieval/  reranking/  pipeline/
      core/                         agent capabilities
        agent_memory/  hierarchical_agents/  planning/  tool_orchestration/
        long_context/  prompting/  replay_analysis/
      serving/                      HTTP serving
        api/
      training/                     offline MLOps
        fine_tuning/  datasets/  experiment_tracking/
      evaluation/                   offline evaluation
        framework/  prompts/  benchmarking/  hallucination/
      config.py                     typed runtime settings
  tests/                            unit/  integration/  fixtures/  conftest.py
  configs/                          default.yaml + observability/
  deploy/                           Dockerfile, docker-compose.yml, .dockerignore
  .github/workflows/ci.yml          CI: ruff + pytest
  pyproject.toml                    metadata, deps, optional extras, ruff + pytest (uv)
  .pre-commit-config.yaml           ruff + hygiene hooks
```

---

## Build system

| Field | Value |
|---|---|
| Build tool | uv (no compilation step — pure Python) |
| Configuration file | pyproject.toml |
| Toolchain | CPython 3.12+, ruff (lint/format), pytest (tests) |
| Optional extras | `rag`, `local-inference`, `training`, `serving`, `data`, `tracking` |

Heavy integrations are NOT in the default install. Subpackage `__init__` files must stay
import-safe (no heavy top-level imports) so the smoke test imports everything without extras.

---

## Standard build sequence

```bash
# From project root — always:
uv sync --extra dev     # create venv + install project and dev deps (light)
uv run ruff check .     # lint
uv run pytest           # run tests

# Install a heavy capability only when a task needs it:
uv sync --extra rag             # or: local-inference / training / serving / data / tracking
```

---

## Targets

Pure-Python project — no compiled targets. The package is `llm_agents`; tests live in
`tests/` (`unit/`, `integration/`). Run a subset with:

```bash
uv run pytest tests/unit -v
uv run pytest -k <pattern> -v
```

---

## Impact matrix

| Change | package (llm_agents) | tests |
|---|---|---|
| Subsystem implementation | import-check | run affected tests |
| Public `__init__` export | import-check | run dependent tests |
| Dependency change (pyproject) | uv sync | run full suite |

---

## Import verification

```bash
uv run python -c "import llm_agents; print('ok')"
```

If import fails — do not proceed; surface to developer.
