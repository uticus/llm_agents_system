"""Data models for prompt variant comparison.

:class:`PromptVariant` holds a named template and metadata.
:class:`VariantResult` pairs a variant with its aggregated :class:`EvalReport`.
:class:`PromptComparison` collects all variant results, ranked by mean score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llm_agents.evaluation.framework._models import EvalReport


@dataclass
class PromptVariant:
    """A named prompt template to be compared against other variants.

    The template is a Python :meth:`str.format_map` compatible string.
    ``{input}`` in the template is replaced with the :class:`EvalCase` input
    at evaluation time.

    Args:
        name:     Short identifier for this variant (e.g. ``"v1-cot"``).
        template: Prompt template string.  Must contain ``{input}``.
        metadata: Arbitrary key-value data (author, version, notes).
    """

    name: str
    template: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def format(self, input_text: str) -> str:
        """Return the template with ``{input}`` replaced by *input_text*."""
        return self.template.format_map({"input": input_text})


@dataclass
class VariantResult:
    """Aggregated evaluation outcome for one :class:`PromptVariant`.

    Args:
        variant: The prompt variant that was evaluated.
        report:  Aggregated :class:`EvalReport` from the harness run.
    """

    variant: PromptVariant
    report: EvalReport

    @property
    def mean_score(self) -> float:
        """Convenience alias for ``report.mean_score``."""
        return self.report.mean_score


@dataclass
class PromptComparison:
    """Ranked collection of :class:`VariantResult` objects.

    Results are sorted by mean score descending at construction time.

    Args:
        results: All variant results (will be sorted in place).
    """

    results: list[VariantResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Stable sort: highest mean_score first.
        self.results = sorted(
            self.results, key=lambda r: r.mean_score, reverse=True
        )

    @property
    def winner(self) -> PromptVariant | None:
        """The variant with the highest mean score, or ``None`` if empty."""
        if not self.results:
            return None
        return self.results[0].variant
