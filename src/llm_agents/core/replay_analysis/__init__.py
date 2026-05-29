"""Replay analysis: load, replay, and analyze recorded agent run traces.

Public surface
--------------
Loading::

    from llm_agents.core.replay_analysis import load_trace

Analysis::

    from llm_agents.core.replay_analysis import analyze, AnalysisReport, SpanSummary

Replay and divergence::

    from llm_agents.core.replay_analysis import ReplayEngine, detect_divergence

Usage example::

    trace = load_trace("traces/my_run.json")
    report = analyze(trace)
    engine = ReplayEngine(trace)
    summaries = engine.replay()
"""

from llm_agents.core.replay_analysis._analyzer import analyze
from llm_agents.core.replay_analysis._loader import load_trace
from llm_agents.core.replay_analysis._replay import ReplayEngine, detect_divergence
from llm_agents.core.replay_analysis._report import AnalysisReport, SpanSummary

__all__ = [
    "AnalysisReport",
    "ReplayEngine",
    "SpanSummary",
    "analyze",
    "detect_divergence",
    "load_trace",
]
