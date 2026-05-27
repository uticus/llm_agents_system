# Module Assignment: Prompting
# Path: src/llm_agents/core/prompting/
# Layer: core
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 25

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Build dynamic few-shot prompts from templates and minimal annotated examples, so new domains
(support queries, lore, gameplay tips) can be onboarded without fine-tuning.

## Background / problem

Few-shot prompting adapts behavior with little data. A template system with example
selection lets the platform tailor prompts per domain and assemble grounded prompts for RAG.

## Scope

### In scope
- A `PromptTemplate` with variable substitution.
- Few-shot example selection (static set, plus a seam for dynamic/similarity selection).
- Prompt assembly that fits a token budget (uses `core/long_context`).
- A small library of base templates (support, lore, gameplay tips) as examples.

### Out of scope
- Prompt evaluation/comparison (owned by `evaluation/prompts`).

## Proposed public surface (for Architect to refine)
- `PromptTemplate`, `FewShotTemplate`, `ExampleSelector`.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- pytest; unit tests must not make real network calls.
- Public surface re-exported from `core/prompting/__init__.py`.

## Dependencies
- `core/long_context` (budget-aware assembly). Soft: `rag/embeddings` (similarity selection).

## Success criteria
- [ ] Templates render with variable substitution.
- [ ] Few-shot examples are injected and the prompt respects a token budget.
- [ ] Tests cover rendering, example injection, and budget trimming.

## Open questions
- Template format (str.format vs a templating lib).
- Static vs similarity-based example selection as the default.
