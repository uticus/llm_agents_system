"""Data models for hierarchical agent coordination.

:class:`AgentResult` carries the outcome of a single agent task.
:class:`SupervisorResult` aggregates results from all delegated subtasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Outcome of a single agent task invocation.

    Args:
        task:    The task string that was assigned.
        output:  Produced value on success, or ``None`` on failure.
        success: ``True`` when the agent completed without error.
        error:   Human-readable error message on failure, else ``None``.
    """

    task: str
    output: Any
    success: bool = True
    error: str | None = None

    @classmethod
    def ok(cls, task: str, output: Any) -> AgentResult:
        """Convenience constructor for a successful result."""
        return cls(task=task, output=output, success=True, error=None)

    @classmethod
    def err(cls, task: str, error: str) -> AgentResult:
        """Convenience constructor for a failed result."""
        return cls(task=task, output=None, success=False, error=error)


@dataclass
class SupervisorResult:
    """Aggregated outcomes of a supervisor run.

    Args:
        goal:         The original goal string.
        results:      One :class:`AgentResult` per delegated subtask, in order.
        success:      ``True`` when all delegated subtasks succeeded.
        failed_count: Number of subtasks that failed.
    """

    goal: str
    results: list[AgentResult] = field(default_factory=list)
    success: bool = True
    failed_count: int = 0
