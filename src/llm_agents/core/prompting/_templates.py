"""PromptTemplate, FewShotTemplate, and ExampleSelector.

:class:`PromptTemplate` wraps a format string with named ``{placeholders}``.

:class:`FewShotTemplate` extends it with a list of (input, output) examples
that are rendered before the user's input.

:class:`ExampleSelector` picks the most relevant examples for a given input
from a pool, using a caller-supplied scorer callable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# PromptTemplate
# ---------------------------------------------------------------------------


@dataclass
class PromptTemplate:
    """A reusable prompt template with named ``{placeholder}`` slots.

    Args:
        template: Format string using Python ``str.format_map`` syntax.
                  Example: ``"You are a helpful assistant.\\n\\nUser: {input}"``
        metadata: Arbitrary metadata (model hint, version, etc.).

    Example::

        tmpl = PromptTemplate("Translate to French: {text}")
        prompt = tmpl.format(text="Hello world")
    """

    template: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def format(self, **kwargs: Any) -> str:
        """Render the template by substituting *kwargs* into placeholders.

        Args:
            **kwargs: Named values matching the ``{placeholders}`` in the
                      template string.

        Returns:
            Rendered prompt string.

        Raises:
            KeyError: If a placeholder in the template has no matching kwarg.
        """
        return self.template.format_map(kwargs)

    @property
    def variables(self) -> list[str]:
        """Return the list of placeholder names in the template.

        Returns:
            Names of all ``{placeholder}`` tokens found in the template,
            in order of first appearance (duplicates removed).
        """
        import string

        formatter = string.Formatter()
        seen: list[str] = []
        for _, field_name, _, _ in formatter.parse(self.template):
            if field_name is not None and field_name not in seen:
                seen.append(field_name)
        return seen


# ---------------------------------------------------------------------------
# FewShotTemplate
# ---------------------------------------------------------------------------


@dataclass
class Example:
    """A single (input, output) training example for few-shot prompting.

    Args:
        input_text:  The user-side example.
        output_text: The expected assistant response.
    """

    input_text: str
    output_text: str


@dataclass
class FewShotTemplate:
    """Prompt template that prepends labelled (input, output) examples.

    Args:
        instruction:    System or task instruction placed at the top.
        examples:       List of :class:`Example` objects shown before the query.
        input_label:    Label for user inputs (default ``"Input"``).
        output_label:   Label for assistant outputs (default ``"Output"``).
        query_label:    Label for the final user query (default ``"Input"``).
        separator:      Separator between examples (default ``"\\n\\n"``).
    """

    instruction: str
    examples: list[Example] = field(default_factory=list)
    input_label: str = "Input"
    output_label: str = "Output"
    query_label: str = "Input"
    separator: str = "\n\n"

    def format(self, query: str) -> str:
        """Render the few-shot prompt.

        Args:
            query: The actual user input appended at the end after the examples.

        Returns:
            Formatted prompt string.
        """
        parts: list[str] = [self.instruction]
        for ex in self.examples:
            block = f"{self.input_label}: {ex.input_text}\n{self.output_label}: {ex.output_text}"
            parts.append(block)
        parts.append(f"{self.query_label}: {query}\n{self.output_label}:")
        return self.separator.join(parts)


# ---------------------------------------------------------------------------
# ExampleSelector
# ---------------------------------------------------------------------------


class ExampleSelector:
    """Select the most relevant examples from a pool for a given query.

    Args:
        examples: Pool of :class:`Example` objects to select from.
        scorer:   Callable ``(query: str, example: Example) -> float``.
                  Higher scores are preferred.
        top_k:    Maximum number of examples to return (default 3).
    """

    def __init__(
        self,
        examples: list[Example],
        scorer: Any,
        top_k: int = 3,
    ) -> None:
        self._examples = list(examples)
        self._scorer = scorer
        self.top_k = top_k

    def select(self, query: str, *, top_k: int | None = None) -> list[Example]:
        """Return up to *top_k* examples most relevant to *query*.

        Args:
            query:  Input text used to score examples.
            top_k:  Override constructor *top_k* for this call.

        Returns:
            Examples sorted by descending relevance score, truncated to *top_k*.
        """
        k = top_k if top_k is not None else self.top_k
        scored = sorted(
            self._examples,
            key=lambda ex: self._scorer(query, ex),
            reverse=True,
        )
        return scored[:k]
