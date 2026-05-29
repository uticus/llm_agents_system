"""Hierarchical agents: supervisor/worker hierarchies, delegation, and coordination.

Public surface
--------------
Data model::

    from llm_agents.core.hierarchical_agents import AgentResult, SupervisorResult

Protocol and implementations::

    from llm_agents.core.hierarchical_agents import Agent, Worker, Supervisor

Usage example::

    worker = Worker(router=router, model="gpt-4o")
    supervisor = Supervisor(planner=planner, workers=[worker])
    result = await supervisor.run("analyze and summarize the dataset")
"""

from llm_agents.core.hierarchical_agents._agent import Agent, Worker
from llm_agents.core.hierarchical_agents._models import AgentResult, SupervisorResult
from llm_agents.core.hierarchical_agents._supervisor import Supervisor

__all__ = [
    "Agent",
    "AgentResult",
    "Supervisor",
    "SupervisorResult",
    "Worker",
]
