"""Connectors: pull documents from PostgreSQL, Confluence, Jira, and Google Drive.

Each source is behind a ``Connector`` interface. Requires the ``data`` extra.

Public surface
--------------
- :class:`Document` — fetched document with content, source metadata, and cursor.
- :class:`Connector` — structural Protocol for external data source connectors.
- :class:`FakeConnector` — deterministic test connector that yields preset documents.
"""

from llm_agents.data.connectors._connector import Connector, FakeConnector
from llm_agents.data.connectors._models import Document

__all__ = [
    "Connector",
    "Document",
    "FakeConnector",
]
