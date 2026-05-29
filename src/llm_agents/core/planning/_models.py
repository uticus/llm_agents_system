"""Data models for the planning subsystem.

Defines :class:`Step` (single executable action), :class:`Plan` (ordered
sequence of steps toward a goal), and the :class:`StepStatus` /
:class:`PlanStatus` enumerations that track execution state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StepStatus(StrEnum):
    """Lifecycle state of a single plan step."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class PlanStatus(StrEnum):
    """Lifecycle state of an entire plan."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Step:
    """A single executable action within a :class:`Plan`.

    Args:
        description:    Human-readable description of what this step does.
        id:             Unique identifier; auto-generated if not provided.
        tool_name:      Name of a registered tool to invoke.  ``None`` means
                        the step is answered by an LLM call.
        tool_arguments: Key-value arguments forwarded to the tool.
        status:         Current execution state.
        result:         Output produced on success, else ``None``.
        error:          Error message on failure, else ``None``.
    """

    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None


@dataclass
class Plan:
    """An ordered sequence of :class:`Step` objects toward a *goal*.

    Args:
        goal:   The original goal string that generated this plan.
        steps:  Ordered list of steps to execute.
        status: Current execution state of the plan as a whole.
    """

    goal: str
    steps: list[Step]
    status: PlanStatus = PlanStatus.PENDING
