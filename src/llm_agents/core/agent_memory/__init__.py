"""Agent memory subsystem: short-term working buffer and long-term recall.

Public surface
--------------
Data model::

    from llm_agents.core.agent_memory import MemoryItem

Short-term buffer::

    from llm_agents.core.agent_memory import ShortTermMemory
    stm = ShortTermMemory(token_budget=2048)
    stm.add(MemoryItem(content="Hello", role="user", timestamp=time.monotonic()))

Long-term store::

    from llm_agents.core.agent_memory import LongTermMemory
    ltm = LongTermMemory()
    ltm.add(item)
    recent = ltm.recent(5)
    hits = ltm.search("what did the user say about X?")

Persistence protocol and default implementation::

    from llm_agents.core.agent_memory import MemoryStore, InMemoryStore
    store: MemoryStore = InMemoryStore()
"""

from llm_agents.core.agent_memory._long_term import InMemoryStore, LongTermMemory, MemoryStore
from llm_agents.core.agent_memory._models import MemoryItem
from llm_agents.core.agent_memory._short_term import ShortTermMemory

__all__ = [
    "InMemoryStore",
    "LongTermMemory",
    "MemoryItem",
    "MemoryStore",
    "ShortTermMemory",
]
