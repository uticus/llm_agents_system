# Module Assignment: Document parsers
# Path: src/llm_agents/data/parsers/
# Layer: data
# Status: backlog -> promote to tasks/inbox/request-NNN.md
# Suggested order: 17

> Module-level assignment. Promote into a request that activates the pipeline. Interface
> sketches are hints for the Architect, not a final design.

## Goal

Extract clean text (and structure where useful) from PDF, DOCX, and custom document formats
behind a uniform `DocumentParser` interface.

## Background / problem

Connectors return raw bytes/files; retrieval needs normalized text. Parsers turn diverse
formats into a consistent document representation for chunking and embedding.

## Scope

### In scope
- A `DocumentParser` interface (bytes/path -> normalized text + metadata).
- Reference parsers: PDF and DOCX (behind the `data` extra), plus a plain-text parser.
- A registry mapping content type / extension to a parser.

### Out of scope
- Fetching documents (owned by `data/connectors`).
- Chunking/embedding (owned by `rag`).

## Proposed public surface (for Architect to refine)
- `DocumentParser` (protocol), `ParserRegistry`, `PdfParser`, `DocxParser`, `TextParser`.

## Constraints
- Python 3.12+, type hints, ruff-clean. English only, no emojis.
- PDF/DOCX libs behind the `data` extra; no heavy imports at module top level.
- pytest; tests use small fixture documents.
- Public surface re-exported from `data/parsers/__init__.py`.

## Dependencies
- None heavy (uses `data` extra libs).

## Success criteria
- [ ] PDF, DOCX, and text inputs parse to normalized text behind one interface.
- [ ] The registry selects the right parser by type/extension.
- [ ] Tests cover each parser with a small fixture.

## Open questions
- How much structure to preserve (headings, tables) vs plain text.
- OCR for scanned PDFs — in scope later?
