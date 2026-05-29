"""Parsers: extract text from PDF, DOCX, and custom document formats.

Behind a ``DocumentParser`` interface. Requires the ``data`` extra.

Public surface
--------------
- :class:`ParsedDocument` — parsed document with extracted text and metadata.
- :class:`DocumentParser` — structural Protocol for document parsers.
- :class:`TextParser` — plain-text parser; decodes bytes/str.
- :class:`ParserRegistry` — maps extension/content-type to a parser.
"""

from llm_agents.data.parsers._models import ParsedDocument
from llm_agents.data.parsers._parser import DocumentParser, TextParser
from llm_agents.data.parsers._registry import ParserRegistry

__all__ = [
    "DocumentParser",
    "ParsedDocument",
    "ParserRegistry",
    "TextParser",
]
