# Module Assignment: Agent memory
# Path: src/llm_agents/core/agent_memory/
# Layer: core
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 5 of 13

> Module-level assignment. To be promoted into a request that activates the pipeline.
> The "proposed public surface" is a hint for the Architect, not a final design.

## Goal

Give agents short-term (working) and long-term memory with a retrieval API and a
persistence seam for external backends.

## Background / problem

Agents need state that outlives a single request: a token-bounded working buffer for the
current task, and durable long-term recall. Without this, every step re-derives context and
the system cannot scale to multi-step work or stay stateless across processes.

## Scope

### In scope
- A memory item model (content, role/type, timestamp, metadata).
- Short-term store: a working/conversation buffer with token-aware trimming.
- Long-term store interface plus an in-memory implementation.
- Retrieval API: recent items and a relevance query (relevance can start as a simple
  keyword/recency stub with a seam for embeddings later).
- A persistence interface so external backends can be added without touching callers.

### Out of scope
- Vector database / embedding implementations (future request).
- Cross-agent shared memory semantics (touched by hierarchical_agents).

## Proposed public surface (for Architect to refine)
- `MemoryItem`, `ShortTermMemory`, `LongTermMemory` (interface + in-memory impl),
  `MemoryStore` persistence protocol.

## Constraints
- Python 3.12+, pure Python, type hints, ruff-clean. English only, no emojis.
- Token-aware trimming may reuse `core/long_context` utilities (soft dependency).
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `core/agent_memory/__init__.py`.

## Dependencies
- Soft: `core/long_context` (trimming/summarization), `infra/tracing`.

## Success criteria
- [ ] Items can be stored and recalled from short- and long-term memory.
- [ ] The working buffer respects a configurable token budget.
- [ ] Retrieval returns a relevant/recent subset.
- [ ] Tests cover trimming, recall, and the persistence interface.

## Open questions
- Embedding/vector backend choice and when to introduce it.
- Serialization format for persisted memory.
