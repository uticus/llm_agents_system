"""Unit tests for evaluation/prompts.

Covers PromptVariant model and template formatting, VariantResult,
PromptComparison ranking, and compare() with a mocked router.
No real network calls.
"""

from __future__ import annotations

import asyncio

import pytest

from llm_agents.evaluation.framework import ContainsMetric, EvalCase, ExactMatchMetric
from llm_agents.evaluation.framework._models import EvalReport
from llm_agents.evaluation.prompts import (
    PromptComparison,
    PromptVariant,
    VariantResult,
    compare,
)
from llm_agents.infra.inference_routing._models import (
    Candidate,
    LLMResponse,
    RoutingPolicy,
)
from llm_agents.infra.inference_routing._provider import FakeProvider
from llm_agents.infra.inference_routing._router import Router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_response(content: str) -> LLMResponse:
    return LLMResponse(
        model="fake",
        content=content,
        prompt_tokens=10,
        completion_tokens=5,
        latency_s=0.0,
    )


def _router_with_responses(*contents: str) -> Router:
    responses = [_fake_response(c) for c in contents]
    provider = FakeProvider("fake", responses)
    policy = RoutingPolicy(candidates=[Candidate(provider=provider, model="fake")])
    return Router(policy, export_hook=None)


def _make_case(input_text: str, expected: str) -> EvalCase:
    return EvalCase(input=input_text, expected_output=expected)


# ---------------------------------------------------------------------------
# T1: PromptVariant
# ---------------------------------------------------------------------------


def test_prompt_variant_format():
    """T1: PromptVariant.format() replaces {input} with the input text."""
    v = PromptVariant(name="v1", template="Answer this: {input}")
    formatted = v.format("what is 2+2?")
    assert formatted == "Answer this: what is 2+2?"


def test_prompt_variant_format_empty_input():
    """T1b: PromptVariant.format() handles empty input strings."""
    v = PromptVariant(name="v1", template="Q: {input} A:")
    assert v.format("") == "Q:  A:"


def test_prompt_variant_defaults():
    """T1c: PromptVariant has empty metadata by default."""
    v = PromptVariant(name="v", template="{input}")
    assert v.metadata == {}


# ---------------------------------------------------------------------------
# T2: VariantResult and PromptComparison
# ---------------------------------------------------------------------------


def _make_variant_result(name: str, mean_score: float) -> VariantResult:
    report = EvalReport(mean_score=mean_score, total_runs=1, pass_rate=float(mean_score >= 0.5))
    variant = PromptVariant(name=name, template="{input}")
    return VariantResult(variant=variant, report=report)


def test_variant_result_mean_score():
    """T2: VariantResult.mean_score proxies report.mean_score."""
    vr = _make_variant_result("v1", 0.75)
    assert vr.mean_score == pytest.approx(0.75)


def test_prompt_comparison_ranks_by_score():
    """T2b: PromptComparison sorts results by mean_score descending."""
    results = [
        _make_variant_result("low", 0.2),
        _make_variant_result("high", 0.9),
        _make_variant_result("mid", 0.5),
    ]
    comp = PromptComparison(results=results)
    assert comp.results[0].variant.name == "high"
    assert comp.results[1].variant.name == "mid"
    assert comp.results[2].variant.name == "low"


def test_prompt_comparison_winner():
    """T2c: PromptComparison.winner returns the highest-scored variant."""
    results = [
        _make_variant_result("v1", 0.3),
        _make_variant_result("v2", 0.8),
    ]
    comp = PromptComparison(results=results)
    assert comp.winner is not None
    assert comp.winner.name == "v2"


def test_prompt_comparison_winner_empty():
    """T2d: PromptComparison.winner returns None when results are empty."""
    comp = PromptComparison(results=[])
    assert comp.winner is None


# ---------------------------------------------------------------------------
# T3: compare()
# ---------------------------------------------------------------------------


def test_compare_two_variants_ranked():
    """T3: compare() evaluates two variants and ranks them by mean_score."""
    # v1 template: the router returns "4" → exact match with expected "4" → score 1.0
    # v2 template: the router returns "wrong" → score 0.0
    # Two cases, two variants → 4 router calls total (alternating v1, v2)
    # FakeProvider cycles: responses are consumed in order.
    # compare() uses a single router that returns responses in order.
    # v1 evaluates case 1 → response "4" (exact match)
    # v2 evaluates case 1 → response "wrong" (no match)
    v1 = PromptVariant(name="good", template="Answer only with the number. {input}")
    v2 = PromptVariant(name="bad", template="Be vague. {input}")

    cases = [_make_case("what is 2+2?", "4")]
    metric = ExactMatchMetric()

    # Since compare() iterates variants sequentially, use a single provider
    # with responses in order: first "4" (for v1), then "wrong" (for v2).
    router = _router_with_responses("4", "wrong")
    comp = asyncio.run(compare([v1, v2], cases, router, metric))

    assert isinstance(comp, PromptComparison)
    assert len(comp.results) == 2
    # "good" variant scored 1.0 (exact match), "bad" scored 0.0
    assert comp.winner is not None
    assert comp.winner.name == "good"
    assert comp.results[0].mean_score == pytest.approx(1.0)
    assert comp.results[1].mean_score == pytest.approx(0.0)


def test_compare_single_variant():
    """T3b: compare() works with a single variant."""
    router = _router_with_responses("yes")
    v = PromptVariant(name="v1", template="{input}")
    cases = [_make_case("is this a test?", "yes")]
    metric = ExactMatchMetric()
    comp = asyncio.run(compare([v], cases, router, metric))
    assert len(comp.results) == 1
    assert comp.winner.name == "v1"
    assert comp.results[0].mean_score == pytest.approx(1.0)


def test_compare_uses_variant_template():
    """T3c: compare() formats each case through the variant template."""
    captured_prompts: list[str] = []

    class CapturingProvider:
        name = "capturing"

        async def complete(self, request):
            captured_prompts.append(request.messages[0]["content"])
            return _fake_response("ok")

    policy = RoutingPolicy([Candidate(CapturingProvider(), "fake")])
    router = Router(policy, export_hook=None)

    v = PromptVariant(name="v", template="PREFIX: {input}")
    cases = [_make_case("hello", "ok")]
    metric = ContainsMetric()
    asyncio.run(compare([v], cases, router, metric))

    assert captured_prompts
    assert captured_prompts[0] == "PREFIX: hello"


def test_compare_empty_variants():
    """T3d: compare() with empty variants returns PromptComparison with no results."""
    router = _router_with_responses("ok")
    cases = [_make_case("q", "a")]
    comp = asyncio.run(compare([], cases, router, ContainsMetric()))
    assert comp.results == []
    assert comp.winner is None


def test_compare_empty_cases():
    """T3e: compare() with empty cases returns reports with zero runs."""
    router = _router_with_responses("ok")
    v = PromptVariant(name="v", template="{input}")
    comp = asyncio.run(compare([v], [], router, ExactMatchMetric()))
    assert len(comp.results) == 1
    assert comp.results[0].report.total_runs == 0
