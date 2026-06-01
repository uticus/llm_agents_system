"""Unit tests for OpenAIEmbedder.

All tests run without an installed openai package.  The OpenAI client is
injected as a plain MagicMock — no sys.modules patching is needed because
the module never imports openai.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedding_item(vector: list[float]) -> MagicMock:
    """Return a mock object resembling openai.types.Embedding."""
    item = MagicMock()
    item.embedding = vector
    return item


def _make_response(vectors: list[list[float]]) -> MagicMock:
    """Return a mock resembling openai.types.CreateEmbeddingResponse."""
    response = MagicMock()
    response.data = [_make_embedding_item(v) for v in vectors]
    return response


def _make_client(vectors: list[list[float]] | None = None) -> MagicMock:
    """Return a mock OpenAI client whose embeddings.create returns *vectors*."""
    if vectors is None:
        vectors = [[1.0, 0.0, 0.0, 0.0]]
    client = MagicMock()
    client.embeddings.create.return_value = _make_response(vectors)
    return client


# ---------------------------------------------------------------------------
# Module-level: no openai import
# ---------------------------------------------------------------------------


class TestOpenAIEmbedderModuleLevel:
    def test_no_openai_import_in_module(self) -> None:
        """openai must not be imported at module level."""
        import ast
        import inspect

        from llm_agents.rag.embeddings import _openai_embedder as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "openai", "openai must not be a top-level import"
            if isinstance(node, ast.ImportFrom):
                if node.module == "openai":
                    assert node.col_offset != 0, "openai must not be a top-level import"

    def test_module_importable_without_openai(self) -> None:
        """The module must be importable even when openai is not installed."""
        import importlib
        import sys

        saved = sys.modules.pop("openai", None)
        try:
            import llm_agents.rag.embeddings._openai_embedder as mod

            importlib.reload(mod)
        except ImportError:
            pytest.fail("Module import must not require openai")
        finally:
            if saved is not None:
                sys.modules["openai"] = saved


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestOpenAIEmbedderProtocol:
    def test_isinstance_embedder(self) -> None:
        from llm_agents.rag.embeddings import Embedder
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client()
        emb = OpenAIEmbedder(client, dimensions=4)
        assert isinstance(emb, Embedder)

    def test_embed_returns_list_of_lists(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client([[0.1, 0.2]])
        emb = OpenAIEmbedder(client, dimensions=2)
        result = emb.embed(["hello"])
        assert isinstance(result, list)
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestOpenAIEmbedderInit:
    def test_client_stored(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client()
        emb = OpenAIEmbedder(client)
        assert emb._client is client

    def test_default_model(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        emb = OpenAIEmbedder(_make_client())
        assert emb.model == "text-embedding-3-small"

    def test_default_dimensions_is_none(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        emb = OpenAIEmbedder(_make_client())
        assert emb._dimensions is None

    def test_custom_model_stored(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        emb = OpenAIEmbedder(_make_client(), model="text-embedding-3-large")
        assert emb.model == "text-embedding-3-large"

    def test_custom_dimensions_stored(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        emb = OpenAIEmbedder(_make_client(), dimensions=256)
        assert emb._dimensions == 256


# ---------------------------------------------------------------------------
# dimensions property
# ---------------------------------------------------------------------------


class TestOpenAIEmbedderDimensions:
    def test_raises_before_any_embed_when_none(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        emb = OpenAIEmbedder(_make_client())
        with pytest.raises(ValueError, match="dimensions"):
            _ = emb.dimensions

    def test_returns_value_set_at_construction(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        emb = OpenAIEmbedder(_make_client(), dimensions=512)
        assert emb.dimensions == 512

    def test_inferred_from_first_embed_response(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client([[0.1, 0.2, 0.3]])  # 3-dim vector
        emb = OpenAIEmbedder(client)
        emb.embed(["test"])
        assert emb.dimensions == 3

    def test_inferred_dimensions_stable_on_second_embed(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client([[0.1, 0.2, 0.3]])
        emb = OpenAIEmbedder(client)
        emb.embed(["first"])
        emb.embed(["second"])
        assert emb.dimensions == 3


# ---------------------------------------------------------------------------
# embed()
# ---------------------------------------------------------------------------


class TestOpenAIEmbedderEmbed:
    def test_empty_list_returns_empty(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        emb = OpenAIEmbedder(_make_client())
        assert emb.embed([]) == []

    def test_empty_does_not_call_api(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client()
        emb = OpenAIEmbedder(client)
        emb.embed([])
        client.embeddings.create.assert_not_called()

    def test_result_count_matches_texts(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        vectors = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        client = _make_client(vectors)
        emb = OpenAIEmbedder(client, dimensions=2)
        result = emb.embed(["a", "b", "c"])
        assert len(result) == 3

    def test_vector_values_match_response(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        expected = [0.1, 0.2, 0.3]
        client = _make_client([expected])
        emb = OpenAIEmbedder(client, dimensions=3)
        result = emb.embed(["hello"])
        assert result[0] == expected

    def test_model_kwarg_passed_to_api(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client([[0.0]])
        emb = OpenAIEmbedder(client, model="text-embedding-3-large", dimensions=1)
        emb.embed(["x"])
        _, kwargs = client.embeddings.create.call_args
        assert kwargs["model"] == "text-embedding-3-large"

    def test_input_kwarg_contains_texts(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client([[0.0]])
        emb = OpenAIEmbedder(client, dimensions=1)
        texts = ["alpha", "beta"]
        emb.embed(texts)
        _, kwargs = client.embeddings.create.call_args
        assert kwargs["input"] == texts

    def test_dimensions_kwarg_forwarded_when_set(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client([[0.0] * 256])
        emb = OpenAIEmbedder(client, dimensions=256)
        emb.embed(["x"])
        _, kwargs = client.embeddings.create.call_args
        assert kwargs["dimensions"] == 256

    def test_dimensions_kwarg_absent_when_not_set(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client([[0.0, 0.0]])
        emb = OpenAIEmbedder(client)
        emb.embed(["x"])
        _, kwargs = client.embeddings.create.call_args
        assert "dimensions" not in kwargs

    def test_create_called_once_per_embed(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client([[0.0]])
        emb = OpenAIEmbedder(client, dimensions=1)
        emb.embed(["a", "b", "c"])
        assert client.embeddings.create.call_count == 1

    def test_multiple_embed_calls_each_call_api(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client([[0.0]])
        emb = OpenAIEmbedder(client, dimensions=1)
        emb.embed(["a"])
        emb.embed(["b"])
        assert client.embeddings.create.call_count == 2

    def test_vector_length_matches_dimensions_kwarg(self) -> None:
        from llm_agents.rag.embeddings._openai_embedder import OpenAIEmbedder

        client = _make_client([[0.1] * 512])
        emb = OpenAIEmbedder(client, dimensions=512)
        result = emb.embed(["hello"])
        assert len(result[0]) == 512
