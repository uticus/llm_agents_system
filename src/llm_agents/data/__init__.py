"""Data ingestion.

Pull documents from external sources, parse them, and feed the RAG indexing pipeline for
continuous ingestion and embedding.

Subsystems:
    connectors   pull from PostgreSQL, Confluence, Jira, Google Drive
    parsers      extract text from PDF, DOCX, and custom formats
    ingestion    continuous pull -> parse -> chunk -> embed pipeline

Requires the ``data`` extra for source/parser backends.
"""

__all__ = [
    "connectors",
    "parsers",
    "ingestion",
]
