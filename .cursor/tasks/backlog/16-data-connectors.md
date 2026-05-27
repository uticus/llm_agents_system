# Module Assignment: Data connectors
# Path: src/llm_agents/data/connectors/
# Layer: data
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 16

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Pull documents from external sources behind a uniform `Connector` interface: PostgreSQL,
Confluence API, Jira REST, and Google Drive.

## Background / problem

Grounded answers require internal knowledge. Connectors are the entry point: they fetch
raw documents (with metadata and change detection) for the ingestion pipeline.

## Scope

### In scope
- A `Connector` interface yielding documents with source metadata and a change cursor.
- Reference connectors: PostgreSQL, Confluence, Jira, Google Drive (behind the `data` extra).
- Incremental fetch (since-last-sync) to support continuous ingestion.

### Out of scope
- Parsing binary formats (owned by `data/parsers`).
- Embedding/indexing (owned by `rag`).

## Proposed public surface (for Architect to refine)
- `Connector` (protocol), `Document`, per-source adapter classes.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- Source clients behind the `data` extra; no heavy imports at module top level.
- pytest; unit tests mock the external sources, never hit real services.
- Public surface re-exported from `data/connectors/__init__.py`.

## Dependencies
- `infra/tracing`.

## Success criteria
- [ ] Each connector yields documents with metadata behind the common interface.
- [ ] Incremental fetch returns only changed documents since a cursor.
- [ ] Tests cover at least one connector with a mocked client + incremental logic.

## Open questions
- Auth/secret handling per source.
- Change-detection strategy (timestamps vs revision ids) per source.
