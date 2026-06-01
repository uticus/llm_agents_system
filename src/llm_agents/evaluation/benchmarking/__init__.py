"""Benchmarking: run agents against task suites and aggregate results.

Public surface
--------------
Data model::

    from llm_agents.evaluation.benchmarking import (
        BenchmarkTask, Suite, TaskResult, BenchmarkReport
    )

Runner::

    from llm_agents.evaluation.benchmarking import BenchmarkRunner

Built-in suites and agents::

    from llm_agents.evaluation.benchmarking import BUILTIN_SUITES, BUILTIN_AGENTS

Usage example::

    suite = Suite(name="my_suite", tasks=[...])
    runner = BenchmarkRunner(agent_fn=my_async_agent)
    report = await runner.run(suite)
    print(report.success_rate)

CLI::

    python -m llm_agents.evaluation.benchmarking --suite arithmetic
    python -m llm_agents.evaluation.benchmarking --suite all
"""

from llm_agents.evaluation.benchmarking._models import (
    BenchmarkReport,
    BenchmarkTask,
    Suite,
    TaskResult,
)
from llm_agents.evaluation.benchmarking._runner import BenchmarkRunner
from llm_agents.evaluation.benchmarking._suites import BUILTIN_AGENTS, BUILTIN_SUITES

__all__ = [
    "BUILTIN_AGENTS",
    "BUILTIN_SUITES",
    "BenchmarkReport",
    "BenchmarkRunner",
    "BenchmarkTask",
    "Suite",
    "TaskResult",
]
