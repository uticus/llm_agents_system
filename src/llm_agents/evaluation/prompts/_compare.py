"""Prompt variant comparison engine.

:func:`compare` evaluates a list of :class:`PromptVariant` objects over a
shared :class:`EvalCase` set.  For each variant, an :class:`EvalHarness` is
built that formats the case input through the variant's template, calls the
router, and scores the response.  Results are aggregated into an
:class:`EvalReport` and ranked by mean score in a :class:`PromptComparison`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from llm_agents.evaluation.framework._harness import EvalHarness, aggregate
from llm_agents.evaluation.prompts._models import PromptComparison, VariantResult

if TYPE_CHECKING:
    from llm_agents.evaluation.framework._models import EvalCase
    from llm_agents.evaluation.prompts._models import PromptVariant


async def compare(
    variants: list[PromptVariant],
    cases: list[EvalCase],
    router: Any,
    metric: Any,
    model: str = "default",
    repeat: int = 1,
    threshold: float = 0.5,
) -> PromptComparison:
    """Compare *variants* on *cases* and return a ranked :class:`PromptComparison`.

    For each variant:
    1. Build an agent function that formats the input through the variant
       template and calls *router*.
    2. Run the :class:`EvalHarness` over *cases* with *repeat* repetitions.
    3. Aggregate into an :class:`EvalReport`.
    4. Collect all :class:`VariantResult` objects and sort by mean score.

    Args:
        variants:  Prompt variants to compare.
        cases:     Shared evaluation cases.
        router:    LLM router (``complete(LLMRequest) -> LLMResponse``).
        metric:    Metric with ``score(expected, actual) -> float``.
        model:     Model name for router calls.
        repeat:    Number of repetitions per case per variant.
        threshold: Passing threshold for :func:`aggregate`.

    Returns:
        :class:`PromptComparison` with variants ranked by mean score.
    """
    from llm_agents.infra.inference_routing._models import LLMRequest

    variant_results: list[VariantResult] = []

    for variant in variants:
        # Capture variant in closure to avoid late-binding issues.
        def _make_agent(v: PromptVariant) -> Any:
            async def agent_fn(input_text: str) -> str:
                prompt = v.format(input_text)
                request = LLMRequest(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                )
                response = await router.complete(request)
                return response.content

            return agent_fn

        harness = EvalHarness(
            agent_fn=_make_agent(variant),
            metric=metric,
            threshold=threshold,
        )
        results = await harness.run(cases, repeat=repeat)
        report = aggregate(results, threshold=threshold)
        variant_results.append(VariantResult(variant=variant, report=report))

    return PromptComparison(results=variant_results)
