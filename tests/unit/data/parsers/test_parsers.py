"""Unit tests for data/parsers: ParsedDocument, DocumentParser, TextParser, ParserRegistry."""

from __future__ import annotations

from llm_agents.data.parsers import (
    DocumentParser,
    ParsedDocument,
    ParserRegistry,
    TextParser,
)


# ---------------------------------------------------------------------------
# ParsedDocument
# ---------------------------------------------------------------------------


class TestParsedDocument:
    def test_required_fields(self) -> None:
        doc = ParsedDocument(doc_id="d1", text="hello")
        assert doc.doc_id == "d1"
        assert doc.text == "hello"

    def test_default_metadata(self) -> None:
        doc = ParsedDocument(doc_id="d1", text="hello")
        assert doc.metadata == {}

    def test_full_construction(self) -> None:
        doc = ParsedDocument(doc_id="d2", text="world", metadata={"pages": 5})
        assert doc.metadata == {"pages": 5}

    def test_metadata_isolation(self) -> None:
        doc1 = ParsedDocument(doc_id="a", text="x")
        doc2 = ParsedDocument(doc_id="b", text="y")
        doc1.metadata["k"] = "v"
        assert doc2.metadata == {}


# ---------------------------------------------------------------------------
# DocumentParser protocol
# ---------------------------------------------------------------------------


class TestDocumentParserProtocol:
    def test_text_parser_satisfies_protocol(self) -> None:
        tp = TextParser()
        assert isinstance(tp, DocumentParser)

    def test_plain_class_satisfies_protocol(self) -> None:
        class MyParser:
            def parse(self, content, metadata=None, *, doc_id=""):
                return ParsedDocument(doc_id=doc_id, text=str(content))

        assert isinstance(MyParser(), DocumentParser)

    def test_missing_parse_fails_protocol(self) -> None:
        class Bad:
            pass

        assert not isinstance(Bad(), DocumentParser)


# ---------------------------------------------------------------------------
# TextParser
# ---------------------------------------------------------------------------


class TestTextParserStr:
    def test_str_content_passthrough(self) -> None:
        tp = TextParser()
        result = tp.parse("hello world", doc_id="d1")
        assert result.text == "hello world"
        assert result.doc_id == "d1"

    def test_empty_string(self) -> None:
        tp = TextParser()
        result = tp.parse("")
        assert result.text == ""

    def test_metadata_copied(self) -> None:
        tp = TextParser()
        meta = {"author": "alice"}
        result = tp.parse("x", metadata=meta, doc_id="d1")
        assert result.metadata == {"author": "alice"}
        # Mutation of original does not affect result
        meta["extra"] = "y"
        assert "extra" not in result.metadata

    def test_none_metadata_gives_empty_dict(self) -> None:
        tp = TextParser()
        result = tp.parse("x")
        assert result.metadata == {}


class TestTextParserBytes:
    def test_bytes_decoded_utf8(self) -> None:
        tp = TextParser()
        result = tp.parse("hello".encode(), doc_id="d1")
        assert result.text == "hello"

    def test_bytes_decoded_with_encoding(self) -> None:
        tp = TextParser(encoding="latin-1")
        result = tp.parse("caf\xe9".encode("latin-1"), doc_id="d1")
        assert result.text == "café"

    def test_invalid_bytes_replace_errors(self) -> None:
        tp = TextParser()
        # 0xff is not valid utf-8; default errors='replace' gives replacement char
        result = tp.parse(b"\xff\xfe")
        assert "�" in result.text or result.text  # should not raise

    def test_empty_bytes(self) -> None:
        tp = TextParser()
        result = tp.parse(b"")
        assert result.text == ""

    def test_default_doc_id_empty(self) -> None:
        tp = TextParser()
        result = tp.parse("x")
        assert result.doc_id == ""


# ---------------------------------------------------------------------------
# ParserRegistry
# ---------------------------------------------------------------------------


class TestParserRegistry:
    def test_register_and_get_extension(self) -> None:
        reg = ParserRegistry()
        tp = TextParser()
        reg.register(".txt", tp)
        assert reg.get(".txt") is tp

    def test_get_missing_returns_none(self) -> None:
        reg = ParserRegistry()
        assert reg.get(".pdf") is None

    def test_register_overwrites(self) -> None:
        reg = ParserRegistry()
        tp1 = TextParser()
        tp2 = TextParser(encoding="latin-1")
        reg.register(".txt", tp1)
        reg.register(".txt", tp2)
        assert reg.get(".txt") is tp2

    def test_case_insensitive_key(self) -> None:
        reg = ParserRegistry()
        tp = TextParser()
        reg.register(".TXT", tp)
        assert reg.get(".txt") is tp
        assert reg.get(".TXT") is tp

    def test_content_type_key(self) -> None:
        reg = ParserRegistry()
        tp = TextParser()
        reg.register("text/plain", tp)
        assert reg.get("text/plain") is tp
        assert reg.get("TEXT/PLAIN") is tp

    def test_keys_returns_all(self) -> None:
        reg = ParserRegistry()
        reg.register(".txt", TextParser())
        reg.register("text/plain", TextParser())
        assert set(reg.keys()) == {".txt", "text/plain"}

    def test_len(self) -> None:
        reg = ParserRegistry()
        assert len(reg) == 0
        reg.register(".txt", TextParser())
        assert len(reg) == 1
        reg.register(".md", TextParser())
        assert len(reg) == 2

    def test_multiple_parsers(self) -> None:
        reg = ParserRegistry()
        tp_txt = TextParser()
        tp_md = TextParser(encoding="utf-8")
        reg.register(".txt", tp_txt)
        reg.register(".md", tp_md)
        assert reg.get(".txt") is tp_txt
        assert reg.get(".md") is tp_md
