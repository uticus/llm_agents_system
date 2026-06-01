"""Unit tests for SentenceTransformerEmbedder.

All tests run without a real sentence-transformers installation.
The ``sentence_transformers`` package is patched into ``sys.modules``
so that the lazy-import path inside ``_get_model`` resolves to a mock.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_st_module(
    dims: int = 4,
    encode_output: np.ndarray | None = None,
) -> tuple[ModuleType, MagicMock]:
    """Return a (fake_st_module, mock_model_instance) pair.

    ``fake_st_module.SentenceTransformer(name, device=...)`` returns
    ``mock_model_instance``.
    """
    if encode_output is None:
        encode_output = np.array([[1.0] + [0.0] * (dims - 1)])

    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = dims
    mock_model.encode.return_value = encode_output

    fake_module = ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = MagicMock(return_value=mock_model)  # type: ignore[attr-defined]

    return fake_module, mock_model


def _make_embedder(dims: int = 4, *, encode_output: np.ndarray | None = None):
    """Return (SentenceTransformerEmbedder instance, mock_model, patched sys.modules)."""
    from llm_agents.rag.embeddings._sentence_transformer_embedder import (
        SentenceTransformerEmbedder,
    )

    fake_module, mock_model = _make_st_module(dims=dims, encode_output=encode_output)
    with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
        emb = SentenceTransformerEmbedder()
        # Trigger lazy load while patch is active
        _ = emb._get_model()
    return emb, mock_model


# ---------------------------------------------------------------------------
# Module-level: no sentence_transformers import at module level
# ---------------------------------------------------------------------------


class TestSTEmbedderModuleLevel:
    def test_module_importable_without_sentence_transformers(self) -> None:
        """The module must not import sentence_transformers at module level."""
        saved = sys.modules.pop("sentence_transformers", None)
        try:
            import importlib

            import llm_agents.rag.embeddings._sentence_transformer_embedder as mod

            importlib.reload(mod)  # re-import while sentence_transformers absent
        except ImportError:
            pytest.fail("Module import must not require sentence_transformers")
        finally:
            if saved is not None:
                sys.modules["sentence_transformers"] = saved

    def test_no_sentence_transformers_name_in_module_source(self) -> None:
        """sentence_transformers must not appear as a top-level import."""
        import ast
        import inspect

        from llm_agents.rag.embeddings import _sentence_transformer_embedder as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        top_level_imports = [
            node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        for node in top_level_imports:
            if isinstance(node, ast.ImportFrom) and node.module == "sentence_transformers":
                assert node.col_offset != 0, (
                    "sentence_transformers must not be a top-level import"
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "sentence_transformers", (
                        "sentence_transformers must not be a top-level import"
                    )

    def test_get_model_raises_import_error_when_not_installed(self) -> None:
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": None}):  # type: ignore[dict-item]
            emb = SentenceTransformerEmbedder()
            with pytest.raises(ImportError, match="sentence-transformers"):
                emb._get_model()


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestSTEmbedderProtocol:
    def test_isinstance_embedder(self) -> None:
        from llm_agents.rag.embeddings import Embedder
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        emb = SentenceTransformerEmbedder()
        assert isinstance(emb, Embedder)

    def test_embed_returns_list_of_lists(self) -> None:
        fake_module, _ = _make_st_module(dims=4)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder()
            result = emb.embed(["hello"])
        assert isinstance(result, list)
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestSTEmbedderInit:
    def test_default_model_name(self) -> None:
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        emb = SentenceTransformerEmbedder()
        assert emb.model_name == "all-MiniLM-L6-v2"

    def test_default_device(self) -> None:
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        emb = SentenceTransformerEmbedder()
        assert emb.device == "cpu"

    def test_default_normalize(self) -> None:
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        emb = SentenceTransformerEmbedder()
        assert emb.normalize_embeddings is True

    def test_custom_model_name_stored(self) -> None:
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        emb = SentenceTransformerEmbedder("BAAI/bge-small-en-v1.5")
        assert emb.model_name == "BAAI/bge-small-en-v1.5"

    def test_custom_device_stored(self) -> None:
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        emb = SentenceTransformerEmbedder(device="cuda")
        assert emb.device == "cuda"

    def test_normalize_false_stored(self) -> None:
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        emb = SentenceTransformerEmbedder(normalize_embeddings=False)
        assert emb.normalize_embeddings is False


# ---------------------------------------------------------------------------
# dimensions property
# ---------------------------------------------------------------------------


class TestSTEmbedderDimensions:
    def test_dimensions_triggers_model_load(self) -> None:
        fake_module, mock_model = _make_st_module(dims=8)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder()
            assert emb._model is None  # not yet loaded
            d = emb.dimensions
        assert d == 8
        mock_model.get_sentence_embedding_dimension.assert_called_once()

    def test_dimensions_cached_after_first_access(self) -> None:
        fake_module, mock_model = _make_st_module(dims=8)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder()
            _ = emb.dimensions
            _ = emb.dimensions
        mock_model.get_sentence_embedding_dimension.assert_called_once()

    def test_dimensions_matches_model(self) -> None:
        fake_module, _ = _make_st_module(dims=384)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder()
            assert emb.dimensions == 384

    def test_dimensions_passed_as_device_kwarg_to_constructor(self) -> None:
        """SentenceTransformer(model_name, device=...) must use the stored device."""
        fake_module, _ = _make_st_module(dims=4)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder("my-model", device="cuda")
            _ = emb.dimensions

        fake_module.SentenceTransformer.assert_called_once_with("my-model", device="cuda")


# ---------------------------------------------------------------------------
# embed()
# ---------------------------------------------------------------------------


class TestSTEmbedderEmbed:
    def test_empty_list_returns_empty(self) -> None:
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        emb = SentenceTransformerEmbedder()
        assert emb.embed([]) == []

    def test_empty_does_not_load_model(self) -> None:
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        emb = SentenceTransformerEmbedder()
        emb.embed([])
        assert emb._model is None

    def test_result_count_matches_texts(self) -> None:
        texts = ["a", "b", "c"]
        encode_out = np.array([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])
        fake_module, _ = _make_st_module(dims=2, encode_output=encode_out)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder()
            result = emb.embed(texts)
        assert len(result) == 3

    def test_vector_length_matches_dimensions(self) -> None:
        encode_out = np.array([[1.0, 0.0, 0.0, 0.0, 0.0, 0.0]])
        fake_module, _ = _make_st_module(dims=6, encode_output=encode_out)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder()
            result = emb.embed(["hello"])
        assert len(result[0]) == 6

    def test_encode_called_with_normalize_true(self) -> None:
        fake_module, mock_model = _make_st_module(dims=4)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder(normalize_embeddings=True)
            emb.embed(["x"])

        _, kwargs = mock_model.encode.call_args
        assert kwargs["normalize_embeddings"] is True

    def test_encode_called_with_normalize_false(self) -> None:
        fake_module, mock_model = _make_st_module(dims=4)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder(normalize_embeddings=False)
            emb.embed(["x"])

        _, kwargs = mock_model.encode.call_args
        assert kwargs["normalize_embeddings"] is False

    def test_encode_called_with_convert_to_numpy_true(self) -> None:
        fake_module, mock_model = _make_st_module(dims=4)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder()
            emb.embed(["x"])

        _, kwargs = mock_model.encode.call_args
        assert kwargs["convert_to_numpy"] is True

    def test_dimensions_inferred_from_embed(self) -> None:
        encode_out = np.array([[0.1, 0.2, 0.3]])
        fake_module, _ = _make_st_module(dims=3, encode_output=encode_out)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder()
            emb._dimensions = None  # ensure not pre-set by dimensions property
            emb.embed(["x"])

        # After embed, dimensions must be known
        assert emb._dimensions == 3

    def test_model_loaded_once_across_multiple_embeds(self) -> None:
        encode_out = np.array([[1.0, 0.0, 0.0, 0.0]])
        fake_module, mock_model = _make_st_module(dims=4, encode_output=encode_out)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder()
            emb.embed(["first"])
            emb.embed(["second"])
            emb.embed(["third"])

        fake_module.SentenceTransformer.assert_called_once()

    def test_encode_receives_texts_list(self) -> None:
        texts = ["alpha", "beta"]
        encode_out = np.array([[1.0, 0.0], [0.0, 1.0]])
        fake_module, mock_model = _make_st_module(dims=2, encode_output=encode_out)
        from llm_agents.rag.embeddings._sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            emb = SentenceTransformerEmbedder()
            emb.embed(texts)

        args, _ = mock_model.encode.call_args
        assert args[0] == texts
