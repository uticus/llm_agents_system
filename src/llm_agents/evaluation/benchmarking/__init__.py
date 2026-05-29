"""Benchmarking: run agents against task suites and aggregate results.

Public surface
--------------
Data model::

    from llm_agents.evaluation.benchmarking import (
        BenchmarkTask, Suite, TaskResult, BenchmarkReport
    )

Runner::

    from llm_agents.evaluation.benchmarking import BenchmarkRunner

Usage example::

    suite = Suite(name="my_suite", tasks=[...])
    runner = BenchmarkRunner(agent_fn=my_async_agent)
    report = await runner.run(suite)
    print(report.success_rate)

CLI::

    python -m llm_agents.evaluation.benchmarking --suite tiny
"""

from llm_agents.evaluation.benchmarking._models import (
    BenchmarkReport,
    BenchmarkTask,
    Suite,
    TaskResult,
)
from llm_agents.evaluation.benchmarking._runner import BenchmarkRunner

__all__ = [
    "BenchmarkReport",
    "BenchmarkRunner",
    "BenchmarkTask",
    "Suite",
    "TaskResult",
]
