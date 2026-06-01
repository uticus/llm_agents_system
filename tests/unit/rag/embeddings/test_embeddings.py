"""Unit tests for rag/embeddings: Embedder, FakeEmbedder, BatchEmbedder."""

from __future__ import annotations

import math

import pytest

from llm_agents.rag.embeddings import BatchEmbedder, Embedder, FakeEmbedder

# ---------------------------------------------------------------------------
# Embedder protocol
# ---------------------------------------------------------------------------


class TestEmbedderProtocol:
    def test_fake_embedder_satisfies_protocol(self) -> None:
        fe = FakeEmbedder(dimensions=4)
        assert isinstance(fe, Embedder)

    def test_plain_class_satisfies_protocol(self) -> None:
        class MyEmb:
            dimensions = 3

            def embed(self, texts: list[str]) -> list[list[float]]:
                return [[0.0] * 3 for _ in texts]

        assert isinstance(MyEmb(), Embedder)

    def test_missing_dimensions_fails_protocol(self) -> None:
        class Bad:
            def embed(self, texts: list[str]) -> list[list[float]]:
                return []

        assert not isinstance(Bad(), Embedder)

    def test_missing_embed_fails_protocol(self) -> None:
        class Bad:
            dimensions = 4

        assert not isinstance(Bad(), Embedder)


# ---------------------------------------------------------------------------
# FakeEmbedder
# ---------------------------------------------------------------------------


class TestFakeEmbedder:
    def test_dimensions_attribute(self) -> None:
        fe = FakeEmbedder(dimensions=8)
        assert fe.dimensions == 8

    def test_default_dimensions(self) -> None:
        fe = FakeEmbedder()
        assert fe.dimensions == 4

    def test_invalid_dimensions_raises(self) -> None:
        with pytest.raises(ValueError):
            FakeEmbedder(dimensions=0)

    def test_embed_returns_correct_count(self) -> None:
        fe = FakeEmbedder(dimensions=4)
        result = fe.embed(["a", "b", "c"])
        assert len(result) == 3

    def test_embed_vector_length_matches_dimensions(self) -> None:
        fe = FakeEmbedder(dimensions=6)
        result = fe.embed(["hello"])
        assert len(result[0]) == 6

    def test_embed_unit_vector(self) -> None:
        fe = FakeEmbedder(dimensions=4)
        vec = fe.embed(["x"])[0]
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-9

    def test_embed_empty_list(self) -> None:
        fe = FakeEmbedder(dimensions=4)
        result = fe.embed([])
        assert result == []

    def test_embed_count_incremented(self) -> None:
        fe = FakeEmbedder(dimensions=4)
        assert fe.embed_count == 0
        fe.embed(["a"])
        fe.embed(["b", "c"])
        assert fe.embed_count == 2

    def test_total_texts_tracked(self) -> None:
        fe = FakeEmbedder(dimensions=4)
        fe.embed(["a", "b"])
        fe.embed(["c"])
        assert fe.total_texts == 3

    def test_all_texts_same_vector(self) -> None:
        fe = FakeEmbedder(dimensions=4)
        result = fe.embed(["hello", "world"])
        assert result[0] == result[1]

    def test_single_dimension(self) -> None:
        fe = FakeEmbedder(dimensions=1)
        result = fe.embed(["x"])
        assert len(result[0]) == 1
        assert abs(result[0][0] - 1.0) < 1e-9  # unit vector in 1D is [1.0]


# ---------------------------------------------------------------------------
# BatchEmbedder
# ---------------------------------------------------------------------------


class TestBatchEmbedder:
    def test_invalid_batch_size_raises(self) -> None:
        with pytest.raises(ValueError):
            BatchEmbedder(FakeEmbedder(), batch_size=0)

    def test_dimensions_delegates_to_inner(self) -> None:
        inner = FakeEmbedder(dimensions=8)
        be = BatchEmbedder(inner, batch_size=2)
        assert be.dimensions == 8

    def test_single_batch_no_split(self) -> None:
        inner = FakeEmbedder(dimensions=4)
        be = BatchEmbedder(inner, batch_size=10)
        texts = ["a", "b", "c"]
        result = be.embed(texts)
        assert len(result) == 3
        assert inner.embed_count == 1

    def test_multiple_batches_split(self) -> None:
        inner = FakeEmbedder(dimensions=4)
        be = BatchEmbedder(inner, batch_size=2)
        texts = ["a", "b", "c", "d", "e"]
        result = be.embed(texts)
        assert len(result) == 5
        assert inner.embed_count == 3  # batches of [2, 2, 1]

    def test_output_order_preserved(self) -> None:
        inner = FakeEmbedder(dimensions=4)
        be = BatchEmbedder(inner, batch_size=2)
        result = be.embed(["x", "y", "z"])
        assert len(result) == 3

    def test_empty_input(self) -> None:
        inner = FakeEmbedder(dimensions=4)
        be = BatchEmbedder(inner, batch_size=2)
        result = be.embed([])
        assert result == []
        assert inner.embed_count == 0

    def test_batch_size_one(self) -> None:
        inner = FakeEmbedder(dimensions=4)
        be = BatchEmbedder(inner, batch_size=1)
        be.embed(["a", "b", "c"])
        assert inner.embed_count == 3
        assert inner.total_texts == 3

    def test_satisfies_embedder_protocol(self) -> None:
        be = BatchEmbedder(FakeEmbedder(dimensions=4), batch_size=2)
        assert isinstance(be, Embedder)
