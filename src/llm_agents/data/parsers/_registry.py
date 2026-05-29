"""ParserRegistry: maps file extensions and content types to DocumentParser instances.

Usage::

    registry = ParserRegistry()
    registry.register(".txt", TextParser())
    registry.register("text/plain", TextParser())
    parser = registry.get(".txt")   # -> TextParser | None
"""

from __future__ import annotations

from llm_agents.data.parsers._parser import DocumentParser


class ParserRegistry:
    """Registry mapping extension or content-type strings to parsers.

    Keys are normalised to lowercase before storage and lookup.
    Extensions should include the leading dot (e.g. ``".txt"``).
    """

    def __init__(self) -> None:
        self._parsers: dict[str, DocumentParser] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, key: str, parser: DocumentParser) -> None:
        """Register *parser* under *key*.

        Args:
            key:    Extension (e.g. ``".txt"``) or content-type
                    (e.g. ``"text/plain"``).  Stored in lowercase.
            parser: Any object that satisfies the :class:`DocumentParser`
                    protocol.
        """
        self._parsers[key.lower()] = parser

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, key: str) -> DocumentParser | None:
        """Return the parser registered under *key*, or ``None``.

        Args:
            key: Extension or content-type to look up (case-insensitive).

        Returns:
            Registered :class:`DocumentParser`, or ``None`` if not found.
        """
        return self._parsers.get(key.lower())

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def keys(self) -> list[str]:
        """Return all registered keys in insertion order."""
        return list(self._parsers)

    def __len__(self) -> int:
        return len(self._parsers)
