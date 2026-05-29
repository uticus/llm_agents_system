"""Short-term (working) memory with a configurable token budget.

Items are stored in a deque ordered oldest-first.  When adding an item would
push the total token count over ``token_budget``, the oldest items are evicted
until there is room.  If the item alone is larger than the budget it is still
accepted as the sole item — otherwise the buffer could starve.
"""

from __future__ import annotations

from collections import deque

from llm_agents.core.agent_memory._models import MemoryItem


class ShortTermMemory:
    """Token-bounded FIFO working buffer.

    Args:
        token_budget: Maximum token count the buffer may hold.  Default 2048.
    """

    def __init__(self, token_budget: int = 2048) -> None:
        self._budget: int = token_budget
        self._buffer: deque[MemoryItem] = deque()
        self._total_tokens: int = 0

    def add(self, item: MemoryItem) -> None:
        """Append *item* to the buffer, evicting oldest items if necessary.

        If the item alone exceeds ``token_budget``, all existing items are
        cleared and the item is accepted as the sole entry.
        """
        # Evict oldest items until there is room (or buffer is empty).
        while self._buffer and self._total_tokens + item.token_count > self._budget:
            removed = self._buffer.popleft()
            self._total_tokens -= removed.token_count
        self._buffer.append(item)
        self._total_tokens += item.token_count

    def items(self) -> list[MemoryItem]:
        """Return all buffered items in oldest-first order."""
        return list(self._buffer)

    def total_tokens(self) -> int:
        """Current total estimated token count of all buffered items."""
        return self._total_tokens

    def clear(self) -> None:
        """Remove all items from the buffer."""
        self._buffer.clear()
        self._total_tokens = 0
