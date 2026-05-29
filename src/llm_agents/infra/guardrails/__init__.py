"""Guardrails: constrain outputs to compliant domains and enforce tone.

Lightweight regex/embedding filters by default, with an optional NVIDIA NeMo Guardrails
adapter behind an interface.

Public surface
--------------
Data model::

    from llm_agents.infra.guardrails import GuardAction, GuardResult

Protocol and built-in guards::

    from llm_agents.infra.guardrails import (
        Guard, RegexFilter, KeywordFilter, RedactFilter, EmbeddingFilter
    )

Chain::

    from llm_agents.infra.guardrails import GuardrailChain

Usage example::

    chain = GuardrailChain([
        KeywordFilter(["secret", "internal"]),
        RegexFilter([r"\\bpassword\\b"], flags=re.IGNORECASE),
    ])
    result = chain.run(output_text)
    if not result.passed:
        # handle block or redact
        ...
"""

from llm_agents.infra.guardrails._chain import GuardrailChain
from llm_agents.infra.guardrails._guards import (
    EmbeddingFilter,
    Guard,
    KeywordFilter,
    RedactFilter,
    RegexFilter,
)
from llm_agents.infra.guardrails._models import GuardAction, GuardResult

__all__ = [
    "EmbeddingFilter",
    "Guard",
    "GuardAction",
    "GuardResult",
    "GuardrailChain",
    "KeywordFilter",
    "RedactFilter",
    "RegexFilter",
]
