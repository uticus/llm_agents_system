"""Prompt evaluation: test, score, and compare prompt variants.

Public surface
--------------
Data model::

    from llm_agents.evaluation.prompts import PromptVariant, VariantResult, PromptComparison

Comparison::

    from llm_agents.evaluation.prompts import compare

Usage example::

    v1 = PromptVariant(name="direct", template="Answer: {input}")
    v2 = PromptVariant(name="cot", template="Think step by step. {input}")
    comparison = await compare([v1, v2], cases, router, metric=ContainsMetric())
    print(comparison.winner.name)
"""

from llm_agents.evaluation.prompts._compare import compare
from llm_agents.evaluation.prompts._models import (
    PromptComparison,
    PromptVariant,
    VariantResult,
)

__all__ = [
    "PromptComparison",
    "PromptVariant",
    "VariantResult",
    "compare",
]
