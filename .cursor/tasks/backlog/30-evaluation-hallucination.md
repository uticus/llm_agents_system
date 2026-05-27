# Module Assignment: Hallucination detection
# Path: src/llm_agents/evaluation/hallucination/
# Layer: evaluation (offline)
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 30

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Detect hallucinations by comparing generated answers against ground-truth snippets (and/or
the retrieved context), producing a per-answer groundedness/hallucination score.

## Background / problem

Hallucination is the dominant failure mode for LLM answers. Detecting unsupported claims
against ground-truth or retrieved context turns "looks plausible" into a measurable signal.

## Scope

### In scope
- A detector interface: (answer, ground-truth/context) -> score + flagged unsupported spans.
- Methods: overlap/entailment against ground-truth snippets; consistency vs retrieved context.
- Integration as metrics in `evaluation/framework` (groundedness, hallucination rate).

### Out of scope
- Preventing hallucinations at generation time (owned by `infra/guardrails` / `rag`).

## Proposed public surface (for Architect to refine)
- `HallucinationDetector` (protocol), `detect(answer, references) -> HallucinationReport`.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- Any model-based scorer goes through the mockable provider boundary.
- pytest; unit tests use fixtures with known supported/unsupported claims.
- Public surface re-exported from `evaluation/hallucination/__init__.py`.

## Dependencies
- `evaluation/framework` (metric integration). Soft: `rag/retrieval` (context), `infra/inference_routing` (LLM-as-judge).

## Success criteria
- [ ] Supported answers score as grounded; unsupported claims are flagged.
- [ ] A groundedness/hallucination metric is exposed to the evaluation framework.
- [ ] Tests cover supported, partially-supported, and unsupported cases.

## Open questions
- Overlap/NLI heuristic vs LLM-as-judge as the default method.
- Span-level vs answer-level flagging granularity.
