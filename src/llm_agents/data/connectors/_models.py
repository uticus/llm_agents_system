"""Data models for the connectors subsystem.

:class:`Document` represents a fetched document with content, source metadata,
and an opaque cursor value for incremental fetch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    """A single document fetched from an external source.

    Args:
        doc_id:  Unique identifier within the source (e.g. page ID, row PK).
        content: Raw text content of the document.
        source:  Source name (connector name or URL).
        metadata: Arbitrary key-value metadata (author, title, url, etc.).
        cursor:  Opaque value representing this document's position in the
                 source's change stream (timestamp, revision ID, etc.).
    """

    doc_id: str
    content: str
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    cursor: Any = None
