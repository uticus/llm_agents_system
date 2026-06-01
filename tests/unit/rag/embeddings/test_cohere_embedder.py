"""Unit tests for CohereEmbedder.

All tests run without an installed cohere package.  The Cohere client is
injected as a plain MagicMock — no sys.modules patching is needed because
the module never imports cohere.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(vectors: list[list[float]]) -> MagicMock:
    """Return a mock resembling a cohere EmbedResponse."""
    response = MagicMock()
    response.embeddings = vectors
    return response


def _make_client(vectors: list[list[float]] | None = None) -> MagicMock:
    """Return a mock Cohere client whose embed() returns *vectors*."""
    if vectors is None:
        vectors = [[1.0, 0.0, 0.0, 0.0]]
    client = MagicMock()
    client.embed.return_value = _make_response(vectors)
    return client


# ---------------------------------------------------------------------------
# Module-level: no cohere import
# ---------------------------------------------------------------------------


class TestCohereEmbedderModuleLevel:
    def test_no_cohere_import_in_module(self) -> None:
        """cohere must not be imported at module level."""
        import ast
        import inspect

        from llm_agents.rag.embeddings import _cohere_embedder as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "cohere", "cohere must not be a top-level import"
            if isinstance(node, ast.ImportFrom):
                if node.module == "cohere":
                    assert node.col_offset != 0, "cohere must not be a top-level import"

    def test_module_importable_without_cohere(self) -> None:
        """The module must be importable even when cohere is not installed."""
        import importlib
        import sys

        saved = sys.modules.pop("cohere", None)
        try:
            import llm_agents.rag.embeddings._cohere_embedder as mod

            importlib.reload(mod)
        except ImportError:
            pytest.fail("Module import must not require cohere")
        finally:
            if saved is not None:
                sys.modules["cohere"] = saved


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestCohereEmbedderProtocol:
    def test_isinstance_embedder(self) -> None:
        from llm_agents.rag.embeddings import Embedder
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        emb = CohereEmbedder(_make_client(), dimensions=4)
        assert isinstance(emb, Embedder)

    def test_embed_returns_list_of_lists(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.1, 0.2]])
        emb = CohereEmbedder(client, dimensions=2)
        result = emb.embed(["hello"])
        assert isinstance(result, list)
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestCohereEmbedderInit:
    def test_client_stored(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client()
        emb = CohereEmbedder(client)
        assert emb._client is client

    def test_default_model(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        emb = CohereEmbedder(_make_client())
        assert emb.model == "embed-english-v3.0"

    def test_default_input_type(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        emb = CohereEmbedder(_make_client())
        assert emb.input_type == "search_document"

    def test_default_dimensions_is_none(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        emb = CohereEmbedder(_make_client())
        assert emb._dimensions is None

    def test_custom_model_stored(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        emb = CohereEmbedder(_make_client(), model="embed-multilingual-v3.0")
        assert emb.model == "embed-multilingual-v3.0"

    def test_custom_input_type_stored(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        emb = CohereEmbedder(_make_client(), input_type="search_query")
        assert emb.input_type == "search_query"

    def test_custom_dimensions_stored(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        emb = CohereEmbedder(_make_client(), dimensions=1024)
        assert emb._dimensions == 1024


# ---------------------------------------------------------------------------
# dimensions property
# ---------------------------------------------------------------------------


class TestCohereEmbedderDimensions:
    def test_raises_before_any_embed_when_none(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        emb = CohereEmbedder(_make_client())
        with pytest.raises(ValueError, match="dimensions"):
            _ = emb.dimensions

    def test_returns_value_set_at_construction(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        emb = CohereEmbedder(_make_client(), dimensions=1024)
        assert emb.dimensions == 1024

    def test_inferred_from_first_embed_response(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.1, 0.2, 0.3]])  # 3-dim vector
        emb = CohereEmbedder(client)
        emb.embed(["test"])
        assert emb.dimensions == 3

    def test_inferred_dimensions_stable_on_second_embed(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.1, 0.2, 0.3]])
        emb = CohereEmbedder(client)
        emb.embed(["first"])
        emb.embed(["second"])
        assert emb.dimensions == 3


# ---------------------------------------------------------------------------
# embed()
# ---------------------------------------------------------------------------


class TestCohereEmbedderEmbed:
    def test_empty_list_returns_empty(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        emb = CohereEmbedder(_make_client())
        assert emb.embed([]) == []

    def test_empty_does_not_call_api(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client()
        emb = CohereEmbedder(client)
        emb.embed([])
        client.embed.assert_not_called()

    def test_result_count_matches_texts(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        vectors = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        client = _make_client(vectors)
        emb = CohereEmbedder(client, dimensions=2)
        result = emb.embed(["a", "b", "c"])
        assert len(result) == 3

    def test_vector_values_match_response(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        expected = [0.1, 0.2, 0.3]
        client = _make_client([expected])
        emb = CohereEmbedder(client, dimensions=3)
        result = emb.embed(["hello"])
        assert result[0] == expected

    def test_texts_kwarg_passed_to_api(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.0]])
        emb = CohereEmbedder(client, dimensions=1)
        texts = ["alpha", "beta"]
        emb.embed(texts)
        _, kwargs = client.embed.call_args
        assert kwargs["texts"] == texts

    def test_model_kwarg_passed_to_api(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.0]])
        emb = CohereEmbedder(client, model="embed-multilingual-v3.0", dimensions=1)
        emb.embed(["x"])
        _, kwargs = client.embed.call_args
        assert kwargs["model"] == "embed-multilingual-v3.0"

    def test_input_type_kwarg_passed_to_api(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.0]])
        emb = CohereEmbedder(client, input_type="search_query", dimensions=1)
        emb.embed(["x"])
        _, kwargs = client.embed.call_args
        assert kwargs["input_type"] == "search_query"

    def test_default_input_type_forwarded(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.0]])
        emb = CohereEmbedder(client, dimensions=1)
        emb.embed(["x"])
        _, kwargs = client.embed.call_args
        assert kwargs["input_type"] == "search_document"

    def test_create_called_once_per_embed(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.0]])
        emb = CohereEmbedder(client, dimensions=1)
        emb.embed(["a", "b", "c"])
        assert client.embed.call_count == 1

    def test_multiple_embed_calls_each_call_api(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.0]])
        emb = CohereEmbedder(client, dimensions=1)
        emb.embed(["a"])
        emb.embed(["b"])
        assert client.embed.call_count == 2

    def test_vector_length_matches_dimensions(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.1] * 1024])
        emb = CohereEmbedder(client, dimensions=1024)
        result = emb.embed(["hello"])
        assert len(result[0]) == 1024

    def test_dimensions_inferred_after_embed(self) -> None:
        from llm_agents.rag.embeddings._cohere_embedder import CohereEmbedder

        client = _make_client([[0.1, 0.2, 0.3, 0.4]])
        emb = CohereEmbedder(client)
        assert emb._dimensions is None
        emb.embed(["x"])
        assert emb._dimensions == 4
