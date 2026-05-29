"""Data models for the parsers subsystem.

:class:`ParsedDocument` represents the output of parsing a raw document,
containing the extracted text and associated metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedDocument:
    """The result of parsing a raw document.

    Args:
        doc_id:   Identifier inherited from the source document.
        text:     Extracted plain text.
        metadata: Arbitrary key-value pairs (author, title, page_count, etc.).
    """

    doc_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
