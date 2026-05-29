"""CLI entrypoint for the benchmarking module.

Usage::

    python -m llm_agents.evaluation.benchmarking --suite tiny

Prints a JSON report to stdout.

The built-in ``tiny`` suite contains three arithmetic tasks answered by a
stub agent that echoes the expected answer (for demonstration/testing only).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from llm_agents.evaluation.benchmarking._models import BenchmarkTask, Suite
from llm_agents.evaluation.benchmarking._runner import BenchmarkRunner


def _build_tiny_suite() -> Suite:
    """Return a minimal three-task demonstration suite."""
    tasks = [
        BenchmarkTask(task_id="t1", input="2+2", expected_output="4"),
        BenchmarkTask(task_id="t2", input="3*3", expected_output="9"),
        BenchmarkTask(task_id="t3", input="10-1", expected_output="9"),
    ]
    return Suite(name="tiny", tasks=tasks)


_SUITES: dict[str, Suite] = {
    "tiny": _build_tiny_suite(),
}

_STUB_ANSWERS: dict[str, str] = {
    "2+2": "4",
    "3*3": "9",
    "10-1": "9",
}


async def _run_suite(suite_name: str) -> dict:
    suite = _SUITES.get(suite_name)
    if suite is None:
        print(f"Unknown suite: {suite_name!r}. Available: {list(_SUITES)}", file=sys.stderr)
        sys.exit(1)

    async def stub_agent(input_text: str) -> str:
        return _STUB_ANSWERS.get(input_text, "")

    runner = BenchmarkRunner(agent_fn=stub_agent)
    report = await runner.run(suite)

    return {
        "suite_name": report.suite_name,
        "success_rate": report.success_rate,
        "mean_tokens": report.mean_tokens,
        "mean_latency_s": report.mean_latency_s,
        "p95_latency_s": report.p95_latency_s,
        "mean_cost_usd": report.mean_cost_usd,
        "cache_hit_rate": report.cache_hit_rate,
        "total_tasks": len(report.task_results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a benchmark suite and print a JSON report."
    )
    parser.add_argument(
        "--suite",
        default="tiny",
        help="Suite name to run (default: tiny).",
    )
    args = parser.parse_args()
    result = asyncio.run(_run_suite(args.suite))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
