"""Tool orchestration: register, validate, and dispatch agent tool calls.

Public surface
--------------
Data model::

    from llm_agents.core.tool_orchestration import Tool, ToolCall, ToolResult

Registry and dispatcher::

    from llm_agents.core.tool_orchestration import ToolRegistry, ToolDispatcher

    registry = ToolRegistry()
    registry.register(Tool(name="add", description="...", parameters={...}, fn=add_fn))
    dispatcher = ToolDispatcher(registry)
    result = await dispatcher.dispatch(ToolCall(name="add", arguments={"a": 1, "b": 2}))
"""

from llm_agents.core.tool_orchestration._dispatcher import ToolDispatcher
from llm_agents.core.tool_orchestration._models import Tool, ToolCall, ToolResult
from llm_agents.core.tool_orchestration._registry import ToolRegistry

__all__ = [
    "Tool",
    "ToolCall",
    "ToolDispatcher",
    "ToolRegistry",
    "ToolResult",
]
