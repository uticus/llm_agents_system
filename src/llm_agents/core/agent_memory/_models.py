"""MemoryItem: the unit of storage for both short- and long-term agent memory."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryItem:
    """A single piece of agent memory.

    Args:
        content:     The text content of this memory.
        role:        Semantic role, e.g. ``"user"``, ``"assistant"``, ``"system"``,
                     ``"observation"``.
        timestamp:   Monotonic timestamp at creation time (``time.monotonic()``).
        metadata:    Arbitrary key-value pairs for caller-defined context
                     (source, confidence, tags, etc.).
        token_count: Estimated token count.  If ``0`` (default), it is
                     automatically estimated as ``ceil(len(content) / 4)``
                     (4 characters ≈ 1 token).  Pass an explicit positive value
                     to override.
    """

    content: str
    role: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0

    def __post_init__(self) -> None:
        if self.token_count == 0:
            # Rough approximation: 1 token ≈ 4 characters.
            # Minimum of 1 to avoid zero-cost items that could loop forever.
            self.token_count = max(1, math.ceil(len(self.content) / 4))
