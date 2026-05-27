"""Core agent capabilities.

Subsystems:
    agent_memory         short- and long-term agent memory
    hierarchical_agents  supervisor/worker agent hierarchies
    planning             goal decomposition and planning strategies
    tool_orchestration   tool registry, dispatch, and execution
    long_context         chunking, summarization, and retrieval over large contexts
    prompting            dynamic few-shot prompt templates
    replay_analysis      analysis of recorded agent run traces
"""

__all__ = [
    "agent_memory",
    "hierarchical_agents",
    "planning",
    "tool_orchestration",
    "long_context",
    "prompting",
    "replay_analysis",
]
