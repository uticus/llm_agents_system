# data/parsers

## Overview

The parsers module converts raw document content — bytes or plain strings arriving from connectors — into structured `ParsedDocument` objects that carry clean text and associated metadata. It defines the `DocumentParser` structural protocol so that specialised parsers for PDF, DOCX, HTML, or any other format can be introduced without changing downstream code. A `ParserRegistry` maps file extensions and MIME content-type strings to registered parser instances, enabling format dispatch in the ingestion pipeline without a large `if/elif` chain. The current concrete implementation, `TextParser`, handles plain-text content and is the baseline upon which format-specific parsers will be added.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `ParsedDocument` | dataclass | Parsed document holding extracted plain text and metadata. |
| `DocumentParser` | Protocol | Structural interface for all document parsers. |
| `TextParser` | class | Plain-text parser: decodes bytes with configurable encoding; accepts str as-is. |
| `ParserRegistry` | class | Maps extension/content-type strings to `DocumentParser` instances. |

### `ParsedDocument`

```python
@dataclass
class ParsedDocument:
    doc_id:   str
    text:     str
    metadata: dict[str, Any] = field(default_factory=dict)
```

`doc_id` is inherited directly from the source `Document`; `text` is the normalized extracted text; `metadata` carries any structured fields the parser was able to extract (page count, author, title, etc.).

### `DocumentParser` Protocol

```python
@runtime_checkable
class DocumentParser(Protocol):
    def parse(
        self,
        content: bytes | str,
        metadata: dict[str, Any] | None = None,
        *,
        doc_id: str = "",
    ) -> ParsedDocument:
        ...
```

The protocol is `@runtime_checkable`. Any class with a matching `parse` method satisfies it without subclassing.

### `TextParser`

```python
class TextParser:
    def __init__(self, encoding: str = "utf-8", errors: str = "replace") -> None: ...
    def parse(
        self,
        content: bytes | str,
        metadata: dict[str, Any] | None = None,
        *,
        doc_id: str = "",
    ) -> ParsedDocument: ...
```

`errors="replace"` ensures that invalid byte sequences never raise; they are replaced with the Unicode replacement character. The `metadata` dict is copied (not referenced) so callers cannot mutate the stored metadata after the fact.

### `ParserRegistry`

```python
class ParserRegistry:
    def __init__(self) -> None: ...
    def register(self, key: str, parser: DocumentParser) -> None: ...
    def get(self, key: str) -> DocumentParser | None: ...
    def keys(self) -> list[str]: ...
    def __len__(self) -> int: ...
```

Keys are normalised to lowercase at both `register` and `get` time, so `.TXT` and `.txt` resolve to the same entry. Extensions should include the leading dot (e.g. `".txt"`).

---

## Architecture

### Conceptual view

```
   [ Document.content ]   (bytes | str)
           |
           v
   [ ParserRegistry ]   -- get(".pdf") -> DocumentParser | None
           |
           v
   [ DocumentParser ]   <-- protocol: parse(content, metadata, doc_id)
           |
           v
   [ ParsedDocument ]   -- doc_id, text, metadata
           |
           v
   IngestionPipeline / Indexer
```

The registry acts as a dispatch table. If no parser is registered for a key, `get` returns `None` and the caller decides whether to skip, error, or fall back to `TextParser`.

### Data flow

1. The ingestion pipeline receives a `Document` from a connector.
2. The pipeline determines the content type from `doc.metadata` (e.g. `content_type` key) or from the `doc_id` file extension.
3. It calls `registry.get(key)` to look up the appropriate parser.
4. The parser's `parse(doc.content, metadata=doc.metadata, doc_id=doc.doc_id)` is called.
5. A `ParsedDocument` is returned with `text` set to the normalized content and `metadata` merged from the source.
6. The `ParsedDocument` moves to the chunker stage inside `IngestionPipeline`.

### Key abstractions

**`ParsedDocument`** separates the act of content extraction from the act of understanding structure. Parsers are only responsible for producing a `text` string; structural understanding (chunking, entity extraction) is handled by subsequent stages.

**`DocumentParser` Protocol** follows the same structural/duck-typed pattern as `Connector`. This keeps the parsers module lightweight: format-specific backends (PyMuPDF for PDF, python-docx for DOCX) can live in optional extras without the protocol itself depending on those heavy libraries.

**`ParserRegistry`** centralises dispatch logic. Without it, every caller would need its own `if extension == ".pdf"` chain. The registry also enables dynamic registration at import time or via plugin discovery patterns.

---

## Design decisions and tradeoffs

- **Decision**: `errors="replace"` is the default in `TextParser`.
  **Why**: Production ingestion should not abort on a single bad byte sequence. Silent replacement is safer than crashing the pipeline.
  **Tradeoff**: Silently corrupted text may reduce retrieval quality; callers wanting strict behaviour must pass `errors="strict"` explicitly.

- **Decision**: `metadata` is copied inside `TextParser.parse`.
  **Why**: Prevents caller mutation of the returned `ParsedDocument.metadata` after the fact, making the dataclass effectively immutable in practice.
  **Tradeoff**: Adds a shallow copy allocation per document. For very large metadata dicts this is negligible but worth noting.

- **Decision**: `ParserRegistry` keys are normalised to lowercase.
  **Why**: File extensions and MIME types are case-insensitive in practice; normalisation avoids duplicate registrations and lookup misses.
  **Tradeoff**: Intentional case-sensitive keys (unusual but possible) are not supported.

- **Decision**: `get` returns `None` rather than raising `KeyError`.
  **Why**: Missing-parser is a common condition (unsupported format) that callers should handle gracefully, not an exceptional error.
  **Tradeoff**: Callers must explicitly check for `None`; an unchecked `None` return passed to downstream code will cause an `AttributeError` rather than a clear `ParserNotFound` error.

- **Decision**: `DocumentParser.parse` is synchronous.
  **Why**: Text extraction from bytes is CPU-bound; async adds overhead with no benefit for pure in-process decoding.
  **Tradeoff**: Parsers that call external services (e.g. a cloud OCR API) must either block or wrap themselves in an executor.

---

## Scaling concerns

`TextParser` is stateless and safe to share across threads or async tasks. The `ParserRegistry` is also stateless after registration; concurrent read access is safe. However:

- **Large documents**: `TextParser` decodes the entire `content` into a single string before returning. Documents larger than available memory will cause OOM. A streaming parse interface would be needed for very large files.
- **Format parsers**: PDF and DOCX parsers (not yet implemented) are typically CPU-intensive. Under high concurrency, they will saturate CPU cores. A process pool or separate worker service is the appropriate scaling path.
- **Registry contention**: If parsers are registered at runtime (not only at startup), concurrent writes to `_parsers` are not thread-safe. In practice, registration should complete before multi-threaded access begins.

---

## Future improvements

- **PDF and DOCX parsers**: Add `PdfParser` (using PyMuPDF or pdfplumber) and `DocxParser` (using python-docx) as optional-extra implementations of the `DocumentParser` protocol.
- **Streaming parse**: Introduce a `StreamingDocumentParser` variant that yields chunks incrementally rather than returning a single large `ParsedDocument`, enabling memory-bounded processing of very large files.
- **Structured metadata extraction**: Extend `ParsedDocument` with a `structured` field for richly typed metadata (page count, headings, language code) extracted during parsing, so downstream chunkers can make smarter decisions.
- **Registry auto-discovery**: Add a `ParserRegistry.discover()` classmethod that reads from an entry-points group, allowing third-party packages to register parsers at install time.
- **Error reporting**: Return a `ParseResult` union (`ParsedDocument | ParseError`) instead of raising, matching the pattern used by `IngestionPipeline` error accumulation.

---

## Usage examples

**Register and use a text parser:**

```python
from llm_agents.data.parsers import ParserRegistry, TextParser

registry = ParserRegistry()
registry.register(".txt", TextParser())
registry.register("text/plain", TextParser())

parser = registry.get(".txt")
if parser is not None:
    result = parser.parse(b"Hello world", doc_id="doc-1")
    print(result.text)   # "Hello world"
```

**Custom encoding:**

```python
from llm_agents.data.parsers import TextParser

parser = TextParser(encoding="latin-1", errors="strict")
result = parser.parse(
    "Ren\xe9 Descartes".encode("latin-1"),
    metadata={"author": "Descartes"},
    doc_id="rene-1",
)
print(result.text)      # "René Descartes"
print(result.metadata)  # {"author": "Descartes"}
```

**Runtime conformance check:**

```python
from llm_agents.data.parsers import DocumentParser, TextParser

parser = TextParser()
assert isinstance(parser, DocumentParser)  # True — runtime_checkable Protocol
```
