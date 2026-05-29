"""Tool registry: register and look up tools by name."""

from __future__ import annotations

from llm_agents.core.tool_orchestration._models import Tool


class ToolRegistry:
    """Stores registered tools by name.

    Registering a tool with a duplicate name overwrites the previous entry.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register *tool*, making it available for dispatch.

        Args:
            tool: Tool definition to register.
        """
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Return the :class:`Tool` registered under *name*, or ``None``."""
        return self._tools.get(name)

    def names(self) -> list[str]:
        """Return the names of all registered tools (alphabetical order)."""
        return sorted(self._tools)

    def all_tools(self) -> list[Tool]:
        """Return all registered tools (alphabetical by name)."""
        return [self._tools[n] for n in sorted(self._tools)]
