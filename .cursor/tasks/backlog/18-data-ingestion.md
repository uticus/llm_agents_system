# Module Assignment: Ingestion pipeline
# Path: src/llm_agents/data/ingestion/
# Layer: data
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 18

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Run continuous ingestion: pull from connectors, parse, chunk, embed, and upsert into the
vector store, with deduplication and incremental updates.

## Background / problem

Knowledge changes over time. Ingestion ties connectors + parsers + RAG indexing into a
repeatable pipeline that keeps the index fresh without re-embedding unchanged content.

## Scope

### In scope
- A pipeline orchestrating connector -> parser -> chunk -> embed -> upsert.
- Deduplication and incremental update (skip unchanged documents via content hash/cursor).
- Batch embedding to control cost/latency.
- A run interface suitable for scheduled/continuous execution.

### Out of scope
- The embedding/index internals (owned by `rag`).
- Source/parser implementations (owned by `data/connectors`, `data/parsers`).

## Proposed public surface (for Architect to refine)
- `IngestionPipeline`, a run/`ingest(source)` entry point, dedup helpers.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- pytest; unit tests use fake connectors/parsers and a fake vector store.
- Public surface re-exported from `data/ingestion/__init__.py`.

## Dependencies
- `data/connectors`, `data/parsers`, `rag/indexing` (chunk+embed+upsert),
  `infra/tracing`, `infra/cost_latency_optimization` (batching).

## Success criteria
- [ ] A run pulls -> parses -> chunks -> embeds -> upserts documents end to end (mocked).
- [ ] Unchanged documents are skipped on a second run.
- [ ] Tests cover the full pipeline with fakes and the dedup path.

## Open questions
- Scheduling mechanism (cron, external trigger) — in scope or left to the caller?
- Failure/retry semantics for a partially failed batch.
