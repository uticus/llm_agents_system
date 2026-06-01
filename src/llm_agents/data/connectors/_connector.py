"""Connector protocol and FakeConnector implementation.

:class:`Connector` is a structural ``Protocol`` — any class with matching
``name`` and ``fetch`` members qualifies.

:class:`FakeConnector` yields preset :class:`Document` objects for tests,
supporting incremental fetch via cursor comparison (integer index or ``None``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from llm_agents.data.connectors._models import Document

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable


@runtime_checkable
class Connector(Protocol):
    """Protocol for external data source connectors.

    Any object with matching ``name`` and ``fetch`` members satisfies this
    interface without needing to inherit from :class:`Connector`.
    """

    name: str

    async def fetch(
        self,
        since_cursor: Any = None,
    ) -> AsyncIterator[Document]:
        """Yield documents from the source.

        Args:
            since_cursor: Opaque cursor from a previous run.  When ``None``,
                          fetch all documents.  When provided, fetch only
                          documents newer than this cursor.

        Yields:
            :class:`Document` objects in source order.
        """
        ...


class FakeConnector:
    """Deterministic test connector that yields preset documents.

    Supports incremental fetch: when ``since_cursor`` is provided as an
    integer, only documents with ``cursor > since_cursor`` are yielded.
    Cursors are assigned as the integer index of each document in the list
    (0-based).

    Args:
        name:      Connector name.
        documents: Preset documents to yield.  Cursors are set automatically
                   to the document's index if not already set.
    """

    def __init__(self, name: str, documents: list[Document]) -> None:
        self.name = name
        # Assign integer cursors if not set
        self._documents: list[Document] = []
        for i, doc in enumerate(documents):
            if doc.cursor is None:
                from dataclasses import replace

                doc = replace(doc, cursor=i)
            self._documents.append(doc)
        self.fetch_count = 0

    async def fetch(self, since_cursor: Any = None) -> AsyncIterator[Document]:
        self.fetch_count += 1
        for doc in self._documents:
            if since_cursor is None or (
                isinstance(doc.cursor, int)
                and isinstance(since_cursor, int)
                and doc.cursor > since_cursor
            ):
                yield doc
