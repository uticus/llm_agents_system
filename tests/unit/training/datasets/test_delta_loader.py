"""Unit tests for DeltaTableLoader.

All tests run without a real ``deltalake`` installation.  The package is
patched into ``sys.modules`` via ``MagicMock``.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from llm_agents.training.datasets import Dataset, DeltaTableLoader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deltalake_mock(rows: list[dict]) -> MagicMock:
    """Return a mock ``deltalake`` module with DeltaTable returning *rows*."""
    mod = MagicMock()
    mock_dt = MagicMock()
    mock_dt.to_pyarrow_table.return_value.to_pylist.return_value = rows
    mod.DeltaTable.return_value = mock_dt
    return mod


# ---------------------------------------------------------------------------
# Module-level: importable without deltalake
# ---------------------------------------------------------------------------


class TestDeltaTableLoaderModuleLevel:
    def test_module_importable_without_deltalake(self) -> None:
        saved = sys.modules.pop("deltalake", None)
        try:
            import importlib

            import llm_agents.training.datasets._delta_loader as mod

            importlib.reload(mod)
        except ImportError:
            pytest.fail("Module must be importable without deltalake")
        finally:
            if saved is not None:
                sys.modules["deltalake"] = saved


# ---------------------------------------------------------------------------
# ImportError
# ---------------------------------------------------------------------------


class TestDeltaTableLoaderImportError:
    def test_raises_import_error_without_deltalake(self) -> None:
        with patch.dict(sys.modules, {"deltalake": None}):  # type: ignore[dict-item]
            with pytest.raises(ImportError, match="deltalake"):
                DeltaTableLoader.load("/some/table")


# ---------------------------------------------------------------------------
# load() — normal path
# ---------------------------------------------------------------------------


class TestDeltaTableLoaderLoad:
    def test_returns_dataset_instance(self) -> None:
        rows = [{"text": "hello", "label": "1"}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/my_table")
        assert isinstance(ds, Dataset)

    def test_correct_number_of_examples(self) -> None:
        rows = [
            {"text": "a", "label": "1"},
            {"text": "b", "label": "0"},
            {"text": "c", "label": "1"},
        ]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/t")
        assert len(ds) == 3

    def test_example_text_and_label(self) -> None:
        rows = [{"text": "hello world", "label": "positive"}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/t")
        ex = ds.examples[0]
        assert ex.text == "hello world"
        assert ex.label == "positive"

    def test_values_coerced_to_str(self) -> None:
        rows = [{"text": 42, "label": 1}]  # non-string columns
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/t")
        ex = ds.examples[0]
        assert isinstance(ex.text, str)
        assert isinstance(ex.label, str)

    def test_extra_columns_go_to_metadata(self) -> None:
        rows = [{"text": "hi", "label": "1", "source": "wiki", "score": 0.9}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/t")
        meta = ds.examples[0].metadata
        assert meta["source"] == "wiki"
        assert meta["score"] == 0.9

    def test_text_label_not_in_metadata(self) -> None:
        rows = [{"text": "hi", "label": "1", "extra": "x"}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/t")
        meta = ds.examples[0].metadata
        assert "text" not in meta
        assert "label" not in meta

    def test_default_name_from_path(self) -> None:
        rows = [{"text": "hi", "label": "1"}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/my_table")
        assert ds.name == "my_table"

    def test_custom_name_used(self) -> None:
        rows = [{"text": "hi", "label": "1"}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/t", name="custom-dataset")
        assert ds.name == "custom-dataset"

    def test_version_passed_to_delta_table(self) -> None:
        rows = [{"text": "hi", "label": "1"}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            DeltaTableLoader.load("/data/t", version=3)
        _, kwargs = mod.DeltaTable.call_args
        assert kwargs.get("version") == 3

    def test_no_version_kwarg_when_none(self) -> None:
        rows = [{"text": "hi", "label": "1"}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            DeltaTableLoader.load("/data/t", version=None)
        _, kwargs = mod.DeltaTable.call_args
        assert "version" not in kwargs

    def test_custom_text_column(self) -> None:
        rows = [{"utterance": "hello", "label": "1"}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/t", text_column="utterance")
        assert ds.examples[0].text == "hello"

    def test_custom_label_column(self) -> None:
        rows = [{"text": "hello", "intent": "greeting"}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/t", label_column="intent")
        assert ds.examples[0].label == "greeting"

    def test_empty_table_returns_empty_dataset(self) -> None:
        mod = _make_deltalake_mock([])
        with patch.dict(sys.modules, {"deltalake": mod}):
            ds = DeltaTableLoader.load("/data/t")
        assert len(ds) == 0
        assert isinstance(ds, Dataset)

    def test_delta_table_called_with_table_path(self) -> None:
        rows = [{"text": "hi", "label": "1"}]
        mod = _make_deltalake_mock(rows)
        with patch.dict(sys.modules, {"deltalake": mod}):
            DeltaTableLoader.load("/data/specific/table")
        args, _ = mod.DeltaTable.call_args
        assert args[0] == "/data/specific/table"
