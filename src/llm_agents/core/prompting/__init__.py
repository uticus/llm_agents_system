"""Prompting: dynamic few-shot prompt templates built from minimal annotated data.

Public surface
--------------
- :class:`PromptTemplate` — format-string template with named placeholders.
- :class:`Example` — (input_text, output_text) training example.
- :class:`FewShotTemplate` — instruction + examples + query renderer.
- :class:`ExampleSelector` — selects top-k relevant examples from a pool.
"""

from llm_agents.core.prompting._templates import (
    Example,
    ExampleSelector,
    FewShotTemplate,
    PromptTemplate,
)

__all__ = [
    "Example",
    "ExampleSelector",
    "FewShotTemplate",
    "PromptTemplate",
]
