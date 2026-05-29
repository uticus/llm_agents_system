"""DocumentParser protocol and TextParser implementation.

:class:`DocumentParser` is a structural ``Protocol`` — any class with a
matching ``parse`` method qualifies without inheriting.

:class:`TextParser` handles plain-text content (bytes or str) and decodes
it to a :class:`ParsedDocument`.
"""

from __future__ import annotations

from typing import Any

from llm_agents.data.parsers._models import ParsedDocument

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable


@runtime_checkable
class DocumentParser(Protocol):
    """Protocol for document parsers.

    Any object with a matching ``parse`` method satisfies this interface
    without needing to inherit from :class:`DocumentParser`.
    """

    def parse(
        self,
        content: bytes | str,
        metadata: dict[str, Any] | None = None,
        *,
        doc_id: str = "",
    ) -> ParsedDocument:
        """Parse raw content into a :class:`ParsedDocument`.

        Args:
            content:  Raw bytes or str content of the document.
            metadata: Optional key-value metadata to attach to the result.
            doc_id:   Identifier to carry through to the parsed document.

        Returns:
            :class:`ParsedDocument` with extracted text and metadata.
        """
        ...


class TextParser:
    """Parser for plain-text documents.

    Decodes bytes to str using the given encoding (default ``utf-8``).
    Strings are accepted as-is; the ``encoding`` is only applied to bytes.

    Args:
        encoding: Character encoding used when ``content`` is bytes.
                  Defaults to ``utf-8``.
        errors:   Codec error-handling mode passed to ``bytes.decode``.
                  Defaults to ``replace`` so invalid bytes never raise.
    """

    def __init__(
        self,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> None:
        self._encoding = encoding
        self._errors = errors

    def parse(
        self,
        content: bytes | str,
        metadata: dict[str, Any] | None = None,
        *,
        doc_id: str = "",
    ) -> ParsedDocument:
        """Decode ``content`` and return a :class:`ParsedDocument`.

        Args:
            content:  Raw bytes or str to parse.
            metadata: Optional metadata dict; copied before storing.
            doc_id:   Identifier carried through to the result.

        Returns:
            :class:`ParsedDocument` with ``text`` set to the decoded string.
        """
        if isinstance(content, bytes):
            text = content.decode(self._encoding, errors=self._errors)
        else:
            text = content
        return ParsedDocument(
            doc_id=doc_id,
            text=text,
            metadata=dict(metadata) if metadata else {},
        )
