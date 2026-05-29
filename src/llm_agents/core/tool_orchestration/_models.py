"""Data model for tool orchestration.

Defines :class:`Tool` (tool definition), :class:`ToolCall` (model-requested
invocation), and :class:`ToolResult` (structured execution outcome).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Tool:
    """A callable tool that an agent can invoke.

    Args:
        name:        Unique identifier used by the model to request the tool.
        description: Human/model-readable description of what the tool does.
        parameters:  JSON-Schema-subset dict describing accepted arguments.
                     Example: ``{"type": "object", "properties": {"x": {"type": "number"}},
                     "required": ["x"]}``.
        fn:          Async callable that executes the tool.  Must accept keyword
                     arguments matching *parameters* and return a JSON-serialisable value.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    fn: Any  # Callable[..., Awaitable[Any]]


@dataclass
class ToolCall:
    """A model-requested tool invocation.

    Args:
        name:      Name of the tool to invoke.
        arguments: Key-value arguments to pass to the tool.
        call_id:   Opaque identifier returned by the model (for correlation).
    """

    name: str
    arguments: dict[str, Any]
    call_id: str = ""


@dataclass(frozen=True)
class ToolResult:
    """Structured outcome of a tool dispatch.

    Args:
        call_id: Echoes :attr:`ToolCall.call_id` for correlation.
        name:    Tool name that was invoked.
        output:  Serialisable result value on success, or ``None`` on error.
        error:   Human-readable error message if the dispatch failed, else ``None``.
        success: ``True`` when the tool executed without error.
    """

    call_id: str
    name: str
    output: Any
    error: str | None = None
    success: bool = True

    @classmethod
    def ok(cls, call_id: str, name: str, output: Any) -> ToolResult:
        """Convenience constructor for a successful result."""
        return cls(call_id=call_id, name=name, output=output, error=None, success=True)

    @classmethod
    def err(cls, call_id: str, name: str, error: str) -> ToolResult:
        """Convenience constructor for an error result."""
        return cls(call_id=call_id, name=name, output=None, error=error, success=False)
