"""Trace loader: read a JSON trace file and return a :class:`Trace`.

Delegates JSON parsing and schema validation to
:func:`~llm_agents.infra.tracing._serialization.deserialize_trace`.
"""

from __future__ import annotations

import json
from pathlib import Path

from llm_agents.infra.tracing._models import Trace
from llm_agents.infra.tracing._serialization import deserialize_trace


def load_trace(path: str | Path) -> Trace:
    """Load a :class:`Trace` from a JSON file at *path*.

    Args:
        path: Filesystem path to a JSON trace file produced by
              :func:`~llm_agents.infra.tracing._serialization.serialize_trace`.

    Returns:
        The deserialized :class:`Trace`.

    Raises:
        FileNotFoundError: If *path* does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: If required trace fields are missing.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return deserialize_trace(data)
