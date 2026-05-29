"""Unit tests for core/tool_orchestration.

Covers tool registration, dispatch, validation, error capture, and tracing.
No real network calls.
"""

from __future__ import annotations

import asyncio

import pytest

from llm_agents.core.tool_orchestration import (
    Tool,
    ToolCall,
    ToolDispatcher,
    ToolRegistry,
    ToolResult,
)
from llm_agents.infra.tracing import get_collector
from llm_agents.infra.tracing._models import SpanKind, SpanStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_collector():
    get_collector().reset()
    yield
    get_collector().reset()


def _registry_with_add() -> tuple[ToolRegistry, ToolDispatcher]:
    """Return a registry+dispatcher with a simple 'add' tool."""

    async def add(a: float, b: float) -> float:
        return a + b

    tool = Tool(
        name="add",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        fn=add,
    )
    registry = ToolRegistry()
    registry.register(tool)
    dispatcher = ToolDispatcher(registry)
    return registry, dispatcher


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


def test_registry_register_and_get():
    """Tool can be registered and retrieved by name."""

    async def noop() -> None:
        pass

    tool = Tool(name="noop", description="Does nothing", parameters={}, fn=noop)
    reg = ToolRegistry()
    reg.register(tool)
    assert reg.get("noop") is tool


def test_registry_unknown_tool_returns_none():
    """Getting an unregistered tool returns None."""
    reg = ToolRegistry()
    assert reg.get("nonexistent") is None


def test_registry_names_alphabetical():
    """names() returns alphabetically sorted tool names."""
    reg = ToolRegistry()
    for name in ["zebra", "apple", "mango"]:
        reg.register(Tool(name=name, description="", parameters={}, fn=lambda: None))
    assert reg.names() == ["apple", "mango", "zebra"]


def test_registry_overwrite():
    """Registering a tool with a duplicate name overwrites the previous."""

    async def v1() -> str:
        return "v1"

    async def v2() -> str:
        return "v2"

    reg = ToolRegistry()
    reg.register(Tool(name="t", description="", parameters={}, fn=v1))
    reg.register(Tool(name="t", description="", parameters={}, fn=v2))
    assert reg.get("t").fn is v2


# ---------------------------------------------------------------------------
# Happy path dispatch
# ---------------------------------------------------------------------------


def test_dispatch_async_tool_success():
    """T1: Async tool dispatched successfully; output is correct."""
    _, dispatcher = _registry_with_add()
    call = ToolCall(name="add", arguments={"a": 3, "b": 4}, call_id="c1")
    result = asyncio.run(dispatcher.dispatch(call))
    assert result.success is True
    assert result.output == pytest.approx(7.0)
    assert result.error is None
    assert result.call_id == "c1"


def test_dispatch_sync_tool_via_thread():
    """T2: Synchronous tool is wrapped in asyncio.to_thread and dispatched."""

    def mul(a: float, b: float) -> float:
        return a * b

    tool = Tool(
        name="mul",
        description="Multiply",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
        fn=mul,
    )
    reg = ToolRegistry()
    reg.register(tool)
    dispatcher = ToolDispatcher(reg)
    result = asyncio.run(dispatcher.dispatch(ToolCall(name="mul", arguments={"a": 5, "b": 6})))
    assert result.success is True
    assert result.output == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_dispatch_unknown_tool_returns_error_result():
    """T3: Dispatching an unknown tool returns a ToolResult with success=False."""
    reg = ToolRegistry()
    dispatcher = ToolDispatcher(reg)
    result = asyncio.run(dispatcher.dispatch(ToolCall(name="ghost", arguments={})))
    assert result.success is False
    assert result.error is not None
    assert "Unknown tool" in result.error
    assert result.output is None


def test_dispatch_missing_required_argument():
    """T4: Missing required argument yields an error ToolResult."""
    _, dispatcher = _registry_with_add()
    call = ToolCall(name="add", arguments={"a": 1})  # b is missing
    result = asyncio.run(dispatcher.dispatch(call))
    assert result.success is False
    assert "Missing required argument" in result.error


def test_dispatch_wrong_argument_type():
    """T5: Wrong argument type yields an error ToolResult."""
    _, dispatcher = _registry_with_add()
    call = ToolCall(name="add", arguments={"a": "not-a-number", "b": 2})
    result = asyncio.run(dispatcher.dispatch(call))
    assert result.success is False
    assert "expected type 'number'" in result.error


# ---------------------------------------------------------------------------
# Tool execution failures captured
# ---------------------------------------------------------------------------


def test_dispatch_tool_exception_captured():
    """T6: A tool that raises an exception returns error ToolResult without re-raising."""

    async def boom(x: int) -> None:
        raise RuntimeError("something went wrong")

    tool = Tool(
        name="boom",
        description="",
        parameters={"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
        fn=boom,
    )
    reg = ToolRegistry()
    reg.register(tool)
    dispatcher = ToolDispatcher(reg)
    result = asyncio.run(dispatcher.dispatch(ToolCall(name="boom", arguments={"x": 1})))
    assert result.success is False
    assert "RuntimeError" in result.error
    assert "something went wrong" in result.error


# ---------------------------------------------------------------------------
# Tracing spans
# ---------------------------------------------------------------------------


def test_dispatch_emits_tool_span():
    """T7: Each dispatch emits a SpanKind.TOOL span in the collector."""
    _, dispatcher = _registry_with_add()
    asyncio.run(dispatcher.dispatch(ToolCall(name="add", arguments={"a": 1, "b": 2})))
    collector = get_collector()
    all_spans = [s for t in collector.all_traces() for s in t.spans]
    tool_spans = [s for s in all_spans if s.kind == SpanKind.TOOL]
    assert len(tool_spans) == 1
    assert tool_spans[0].attributes["tool_name"] == "add"
    assert tool_spans[0].status == SpanStatus.OK


def test_dispatch_error_span_has_error_status():
    """T8: Failed dispatch emits a span with ERROR status."""
    reg = ToolRegistry()
    dispatcher = ToolDispatcher(reg)
    asyncio.run(dispatcher.dispatch(ToolCall(name="unknown", arguments={})))
    collector = get_collector()
    all_spans = [s for t in collector.all_traces() for s in t.spans]
    tool_spans = [s for s in all_spans if s.kind == SpanKind.TOOL]
    assert tool_spans[0].status == SpanStatus.ERROR


# ---------------------------------------------------------------------------
# ToolResult constructors
# ---------------------------------------------------------------------------


def test_tool_result_ok():
    """ok() convenience constructor sets success=True."""
    r = ToolResult.ok("id1", "add", 42)
    assert r.success is True
    assert r.output == 42
    assert r.error is None


def test_tool_result_err():
    """err() convenience constructor sets success=False."""
    r = ToolResult.err("id1", "add", "bad args")
    assert r.success is False
    assert r.output is None
    assert r.error == "bad args"
