"""Unit tests for data/connectors: Document, Connector, FakeConnector."""

from __future__ import annotations

import asyncio

from llm_agents.data.connectors import Connector, Document, FakeConnector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect(aiter) -> list[Document]:
    return [doc async for doc in aiter]


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class TestDocument:
    def test_required_fields(self) -> None:
        doc = Document(doc_id="d1", content="hello")
        assert doc.doc_id == "d1"
        assert doc.content == "hello"

    def test_defaults(self) -> None:
        doc = Document(doc_id="d1", content="hello")
        assert doc.source == ""
        assert doc.metadata == {}
        assert doc.cursor is None

    def test_full_construction(self) -> None:
        doc = Document(
            doc_id="d2",
            content="world",
            source="wiki",
            metadata={"author": "alice"},
            cursor=42,
        )
        assert doc.source == "wiki"
        assert doc.metadata == {"author": "alice"}
        assert doc.cursor == 42

    def test_metadata_isolation(self) -> None:
        doc1 = Document(doc_id="a", content="x")
        doc2 = Document(doc_id="b", content="y")
        doc1.metadata["k"] = "v"
        assert doc2.metadata == {}


# ---------------------------------------------------------------------------
# Connector protocol
# ---------------------------------------------------------------------------


class TestConnectorProtocol:
    def test_fake_connector_satisfies_protocol(self) -> None:
        fc = FakeConnector("src", [])
        assert isinstance(fc, Connector)

    def test_plain_class_satisfies_protocol(self) -> None:
        class MyConn:
            name = "mine"

            async def fetch(self, since_cursor=None):
                yield Document(doc_id="x", content="y")

        assert isinstance(MyConn(), Connector)

    def test_missing_name_fails_protocol(self) -> None:
        class Bad:
            async def fetch(self, since_cursor=None):
                yield Document(doc_id="x", content="y")

        assert not isinstance(Bad(), Connector)

    def test_missing_fetch_fails_protocol(self) -> None:
        class Bad:
            name = "bad"

        assert not isinstance(Bad(), Connector)


# ---------------------------------------------------------------------------
# FakeConnector — full fetch
# ---------------------------------------------------------------------------


class TestFakeConnectorFullFetch:
    def test_yields_all_documents(self) -> None:
        docs = [
            Document(doc_id="a", content="alpha"),
            Document(doc_id="b", content="beta"),
            Document(doc_id="c", content="gamma"),
        ]
        fc = FakeConnector("test", docs)
        result = asyncio.run(_collect(fc.fetch()))
        assert [d.doc_id for d in result] == ["a", "b", "c"]

    def test_empty_connector(self) -> None:
        fc = FakeConnector("empty", [])
        result = asyncio.run(_collect(fc.fetch()))
        assert result == []

    def test_cursors_assigned_automatically(self) -> None:
        docs = [Document(doc_id=str(i), content="x") for i in range(3)]
        fc = FakeConnector("c", docs)
        result = asyncio.run(_collect(fc.fetch()))
        assert [d.cursor for d in result] == [0, 1, 2]

    def test_existing_cursor_preserved(self) -> None:
        docs = [
            Document(doc_id="a", content="x", cursor=100),
            Document(doc_id="b", content="y"),
        ]
        fc = FakeConnector("c", docs)
        result = asyncio.run(_collect(fc.fetch()))
        assert result[0].cursor == 100
        assert result[1].cursor == 1

    def test_fetch_count_incremented(self) -> None:
        fc = FakeConnector("c", [Document(doc_id="a", content="x")])
        assert fc.fetch_count == 0
        asyncio.run(_collect(fc.fetch()))
        asyncio.run(_collect(fc.fetch()))
        assert fc.fetch_count == 2

    def test_source_metadata_preserved(self) -> None:
        doc = Document(doc_id="x", content="y", source="s3", metadata={"key": "val"})
        fc = FakeConnector("c", [doc])
        result = asyncio.run(_collect(fc.fetch()))
        assert result[0].source == "s3"
        assert result[0].metadata == {"key": "val"}


# ---------------------------------------------------------------------------
# FakeConnector — incremental fetch (since_cursor)
# ---------------------------------------------------------------------------


class TestFakeConnectorIncrementalFetch:
    def test_since_cursor_filters(self) -> None:
        docs = [Document(doc_id=str(i), content="x") for i in range(5)]
        fc = FakeConnector("c", docs)
        result = asyncio.run(_collect(fc.fetch(since_cursor=2)))
        assert [d.cursor for d in result] == [3, 4]

    def test_since_cursor_zero_skips_first(self) -> None:
        docs = [Document(doc_id=str(i), content="x") for i in range(3)]
        fc = FakeConnector("c", docs)
        result = asyncio.run(_collect(fc.fetch(since_cursor=0)))
        assert [d.cursor for d in result] == [1, 2]

    def test_since_cursor_at_last_yields_nothing(self) -> None:
        docs = [Document(doc_id=str(i), content="x") for i in range(3)]
        fc = FakeConnector("c", docs)
        result = asyncio.run(_collect(fc.fetch(since_cursor=2)))
        assert result == []

    def test_none_cursor_returns_all(self) -> None:
        docs = [Document(doc_id=str(i), content="x") for i in range(4)]
        fc = FakeConnector("c", docs)
        result = asyncio.run(_collect(fc.fetch(since_cursor=None)))
        assert len(result) == 4

    def test_non_int_cursor_skips_comparison(self) -> None:
        """Non-integer doc cursors are not yielded when since_cursor is int."""
        docs = [
            Document(doc_id="a", content="x", cursor="abc"),
            Document(doc_id="b", content="y", cursor="xyz"),
        ]
        fc = FakeConnector("c", docs)
        # since_cursor is int but doc cursors are str — no match, nothing yielded
        result = asyncio.run(_collect(fc.fetch(since_cursor=0)))
        assert result == []

    def test_incremental_simulates_pagination(self) -> None:
        docs = [Document(doc_id=str(i), content="x") for i in range(6)]
        fc = FakeConnector("c", docs)
        # First fetch: all
        page1 = asyncio.run(_collect(fc.fetch()))
        last_cursor = page1[-1].cursor
        # Second fetch on same connector: nothing new
        page2 = asyncio.run(_collect(fc.fetch(since_cursor=last_cursor)))
        assert page2 == []
        # New connector with an extra doc
        docs2 = docs + [Document(doc_id="6", content="new")]
        fc2 = FakeConnector("c", docs2)
        page3 = asyncio.run(_collect(fc2.fetch(since_cursor=last_cursor)))
        assert len(page3) == 1
        assert page3[0].doc_id == "6"
