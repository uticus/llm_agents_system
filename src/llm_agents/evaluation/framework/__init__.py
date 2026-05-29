"""Evaluation framework: metrics, harness, scoring, and variance-aware reports.

Public surface
--------------
Data model::

    from llm_agents.evaluation.framework import EvalCase, EvalResult, EvalReport

Metrics::

    from llm_agents.evaluation.framework import (
        Metric, ExactMatchMetric, ContainsMetric, NormalizedMatchMetric
    )

Harness and aggregation::

    from llm_agents.evaluation.framework import EvalHarness, aggregate

Usage example::

    async def my_agent(input: str) -> str:
        return "answer"

    harness = EvalHarness(agent_fn=my_agent, metric=ExactMatchMetric())
    results = await harness.run(cases, repeat=3)
    report = aggregate(results)
"""

from llm_agents.evaluation.framework._harness import EvalHarness, aggregate
from llm_agents.evaluation.framework._metrics import (
    ContainsMetric,
    ExactMatchMetric,
    Metric,
    NormalizedMatchMetric,
)
from llm_agents.evaluation.framework._models import EvalCase, EvalReport, EvalResult

__all__ = [
    "ContainsMetric",
    "EvalCase",
    "EvalHarness",
    "EvalReport",
    "EvalResult",
    "ExactMatchMetric",
    "Metric",
    "NormalizedMatchMetric",
    "aggregate",
]
