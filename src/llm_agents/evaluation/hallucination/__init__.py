"""Hallucination detection: compare generations against ground-truth snippets.

Public surface
--------------
- :class:`HallucinationReport` — groundedness score, is_hallucination flag, unsupported spans.
- :class:`HallucinationDetector` — structural Protocol for detectors.
- :class:`OverlapDetector` — word-overlap recall heuristic (no model deps).
- :class:`LLMJudgeDetector` — delegates to a caller-supplied scorer callable.
"""

from llm_agents.evaluation.hallucination._detector import (
    HallucinationDetector,
    HallucinationReport,
    LLMJudgeDetector,
    OverlapDetector,
)

__all__ = [
    "HallucinationDetector",
    "HallucinationReport",
    "LLMJudgeDetector",
    "OverlapDetector",
]
