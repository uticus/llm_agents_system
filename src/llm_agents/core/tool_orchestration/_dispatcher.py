"""Tool dispatcher: validate arguments and execute tools safely.

:class:`ToolDispatcher` maps a :class:`ToolCall` to a registered :class:`Tool`,
validates the supplied arguments against the tool's parameter schema, executes
the tool coroutine, and returns a :class:`ToolResult`.  Tool failures are
captured as structured errors — they never propagate as unhandled exceptions.

A :data:`SpanKind.TOOL` tracing span is emitted for each dispatch attempt.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from llm_agents.core.tool_orchestration._models import Tool, ToolCall, ToolResult
from llm_agents.core.tool_orchestration._registry import ToolRegistry
from llm_agents.infra.tracing import tracer
from llm_agents.infra.tracing._models import SpanKind, SpanStatus


def _validate_arguments(tool: Tool, arguments: dict[str, Any]) -> str | None:
    """Validate *arguments* against the tool's parameter schema.

    Performs a minimal JSON-Schema-subset check:
    - ``required`` keys must all be present.
    - ``type`` check for top-level properties (``"string"``, ``"number"``,
      ``"integer"``, ``"boolean"``, ``"object"``, ``"array"``).

    Returns ``None`` if valid, or a human-readable error string.
    """
    schema = tool.parameters
    if not isinstance(schema, dict):
        return None  # no schema — accept all

    required = schema.get("required", [])
    for key in required:
        if key not in arguments:
            return f"Missing required argument: '{key}'"

    properties = schema.get("properties", {})
    type_map: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    for key, value in arguments.items():
        prop_schema = properties.get(key, {})
        expected_type_name = prop_schema.get("type")
        if expected_type_name and expected_type_name in type_map:
            expected_type = type_map[expected_type_name]
            if not isinstance(value, expected_type):
                return (
                    f"Argument '{key}' expected type '{expected_type_name}', "
                    f"got '{type(value).__name__}'"
                )
    return None


class ToolDispatcher:
    """Validates and executes tool calls from a :class:`ToolRegistry`.

    Args:
        registry: The :class:`ToolRegistry` to look up tools from.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def dispatch(self, call: ToolCall) -> ToolResult:
        """Dispatch *call* to the registered tool and return a :class:`ToolResult`.

        Steps:
        1. Look up the tool by name — unknown tool → error result.
        2. Validate arguments against the schema — invalid → error result.
        3. Execute the tool coroutine (wrapping sync callables via
           :func:`asyncio.to_thread`).
        4. Capture any exception as a structured error result.

        A :data:`SpanKind.TOOL` span is emitted for every dispatch attempt.

        Args:
            call: The tool invocation requested by the model.

        Returns:
            A :class:`ToolResult` — always, never raises.
        """
        async with tracer.span(
            f"tool:{call.name}",
            kind=SpanKind.TOOL,
            tool_name=call.name,
            call_id=call.call_id,
        ) as span:
            # 1. Look up tool
            tool = self._registry.get(call.name)
            if tool is None:
                span.status = SpanStatus.ERROR
                span.attributes["error"] = f"Unknown tool: '{call.name}'"
                return ToolResult.err(call.call_id, call.name, f"Unknown tool: '{call.name}'")

            # 2. Validate arguments
            validation_error = _validate_arguments(tool, call.arguments)
            if validation_error:
                span.status = SpanStatus.ERROR
                span.attributes["error"] = validation_error
                return ToolResult.err(call.call_id, call.name, validation_error)

            # 3. Execute
            try:
                if inspect.iscoroutinefunction(tool.fn):
                    output = await tool.fn(**call.arguments)
                else:
                    output = await asyncio.to_thread(tool.fn, **call.arguments)
                span.status = SpanStatus.OK
                return ToolResult.ok(call.call_id, call.name, output)
            except Exception as exc:  # noqa: BLE001
                error_msg = f"{type(exc).__name__}: {exc}"
                span.status = SpanStatus.ERROR
                span.attributes["error"] = error_msg
                return ToolResult.err(call.call_id, call.name, error_msg)
