"""CLI entrypoint for the benchmarking module.

Usage::

    # Run a single built-in suite:
    python -m llm_agents.evaluation.benchmarking --suite arithmetic

    # Run all built-in suites and print a JSON array of reports:
    python -m llm_agents.evaluation.benchmarking --suite all

Prints a JSON report (dict for a single suite, list of dicts for ``all``)
to stdout.

Built-in suites
---------------
- ``tiny``          — 3 arithmetic tasks (demo / smoke test)
- ``arithmetic``    — 50 arithmetic expressions
- ``qa_lookup``     — 30 factual Q&A pairs
- ``hallucination`` — 25 passage/claim verification tasks
- ``classification``— 20 sentiment classification tasks
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from llm_agents.evaluation.benchmarking._runner import BenchmarkRunner
from llm_agents.evaluation.benchmarking._suites import BUILTIN_AGENTS, BUILTIN_SUITES


def _report_to_dict(report: object) -> dict:
    return {
        "suite_name": report.suite_name,  # type: ignore[union-attr]
        "success_rate": report.success_rate,  # type: ignore[union-attr]
        "mean_tokens": report.mean_tokens,  # type: ignore[union-attr]
        "mean_latency_s": report.mean_latency_s,  # type: ignore[union-attr]
        "p95_latency_s": report.p95_latency_s,  # type: ignore[union-attr]
        "mean_cost_usd": report.mean_cost_usd,  # type: ignore[union-attr]
        "cache_hit_rate": report.cache_hit_rate,  # type: ignore[union-attr]
        "total_tasks": len(report.task_results),  # type: ignore[union-attr]
    }


async def _run_single(suite_name: str) -> dict:
    suite = BUILTIN_SUITES.get(suite_name)
    if suite is None:
        available = list(BUILTIN_SUITES) + ["all"]
        print(
            f"Unknown suite: {suite_name!r}. Available: {available}",
            file=sys.stderr,
        )
        sys.exit(1)
    agent_fn = BUILTIN_AGENTS[suite_name]
    runner = BenchmarkRunner(agent_fn=agent_fn)
    report = await runner.run(suite)
    return _report_to_dict(report)


async def _run_suite(suite_name: str) -> dict | list[dict]:
    if suite_name == "all":
        results: list[dict] = []
        for name in BUILTIN_SUITES:
            results.append(await _run_single(name))
        return results
    return await _run_single(suite_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a benchmark suite and print a JSON report.")
    parser.add_argument(
        "--suite",
        default="tiny",
        help=(f"Suite name to run (default: tiny).  Available: {list(BUILTIN_SUITES) + ['all']}"),
    )
    args = parser.parse_args()
    result = asyncio.run(_run_suite(args.suite))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
