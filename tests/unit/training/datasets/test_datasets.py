"""Unit tests for training/datasets: Example, Dataset, DatasetLoader, from_prodigy."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from llm_agents.training.datasets import Dataset, DatasetLoader, Example, from_prodigy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_examples(n: int) -> list[Example]:
    return [Example(text=f"text{i}", label="pos" if i % 2 == 0 else "neg") for i in range(n)]


def _make_dataset(n: int = 10, name: str = "test") -> Dataset:
    return Dataset(name=name, examples=_make_examples(n))


# ---------------------------------------------------------------------------
# Example
# ---------------------------------------------------------------------------


class TestExample:
    def test_required_fields(self) -> None:
        ex = Example(text="hello", label="pos")
        assert ex.text == "hello"
        assert ex.label == "pos"

    def test_default_metadata(self) -> None:
        ex = Example(text="x", label="y")
        assert ex.metadata == {}

    def test_metadata_stored(self) -> None:
        ex = Example(text="x", label="y", metadata={"source": "wiki"})
        assert ex.metadata["source"] == "wiki"

    def test_metadata_isolation(self) -> None:
        ex1 = Example(text="a", label="x")
        ex2 = Example(text="b", label="y")
        ex1.metadata["k"] = "v"
        assert ex2.metadata == {}


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


class TestDataset:
    def test_required_fields(self) -> None:
        ds = Dataset(name="ds")
        assert ds.name == "ds"

    def test_version_auto_generated(self) -> None:
        ds = Dataset(name="ds", examples=_make_examples(3))
        assert len(ds.version) == 32  # MD5 hex

    def test_version_deterministic(self) -> None:
        ds1 = Dataset(name="ds", examples=_make_examples(3))
        ds2 = Dataset(name="ds", examples=_make_examples(3))
        assert ds1.version == ds2.version

    def test_version_changes_with_content(self) -> None:
        ds1 = Dataset(name="ds", examples=_make_examples(3))
        ds2 = Dataset(name="ds", examples=_make_examples(4))
        assert ds1.version != ds2.version

    def test_explicit_version_preserved(self) -> None:
        ds = Dataset(name="ds", version="myversion")
        assert ds.version == "myversion"

    def test_len(self) -> None:
        ds = _make_dataset(7)
        assert len(ds) == 7

    def test_empty_len(self) -> None:
        ds = Dataset(name="ds")
        assert len(ds) == 0


class TestDatasetSplit:
    def test_split_sum_equals_total(self) -> None:
        ds = _make_dataset(10)
        train, val = ds.split(0.8)
        assert len(train) + len(val) == 10

    def test_split_ratio(self) -> None:
        ds = _make_dataset(10)
        train, _ = ds.split(0.8)
        assert len(train) == 8

    def test_split_names(self) -> None:
        ds = Dataset(name="mydata", examples=_make_examples(5))
        train, val = ds.split()
        assert "train" in train.name
        assert "val" in val.name

    def test_split_no_overlap(self) -> None:
        ds = _make_dataset(10)
        train, val = ds.split(0.7)
        train_texts = {e.text for e in train.examples}
        val_texts = {e.text for e in val.examples}
        assert not train_texts & val_texts

    def test_split_small_dataset(self) -> None:
        ds = Dataset(name="ds", examples=[Example(text="x", label="y")])
        train, val = ds.split(0.8)
        # Minimum 1 example in train
        assert len(train) >= 1


class TestDatasetValidate:
    def test_empty_dataset_issue(self) -> None:
        ds = Dataset(name="ds")
        issues = ds.validate()
        assert any("empty" in i.lower() for i in issues)

    def test_empty_text_issue(self) -> None:
        ds = Dataset(name="ds", examples=[
            Example(text="", label="pos"),
            Example(text="good", label="neg"),
        ])
        issues = ds.validate()
        assert any("empty text" in i for i in issues)

    def test_empty_label_issue(self) -> None:
        ds = Dataset(name="ds", examples=[
            Example(text="good text", label=""),
        ])
        issues = ds.validate()
        assert any("empty label" in i for i in issues)

    def test_single_label_issue(self) -> None:
        ds = Dataset(name="ds", examples=[
            Example(text=f"t{i}", label="pos") for i in range(5)
        ])
        issues = ds.validate()
        assert any("one unique label" in i for i in issues)

    def test_valid_dataset_no_issues(self) -> None:
        ds = _make_dataset(10)
        assert ds.validate() == []


# ---------------------------------------------------------------------------
# DatasetLoader
# ---------------------------------------------------------------------------


class TestDatasetLoaderFromExamples:
    def test_basic(self) -> None:
        ds = DatasetLoader.from_examples("test", [("hello", "pos"), ("world", "neg")])
        assert len(ds) == 2
        assert ds.examples[0].text == "hello"
        assert ds.examples[0].label == "pos"

    def test_empty(self) -> None:
        ds = DatasetLoader.from_examples("empty", [])
        assert len(ds) == 0

    def test_name_preserved(self) -> None:
        ds = DatasetLoader.from_examples("my_dataset", [("x", "y")])
        assert ds.name == "my_dataset"


class TestDatasetLoaderFromJsonl:
    def test_basic(self) -> None:
        lines = [
            json.dumps({"text": "hello", "label": "pos"}),
            json.dumps({"text": "world", "label": "neg"}),
        ]
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("\n".join(lines))
            fname = f.name
        ds = DatasetLoader.from_jsonl(fname)
        assert len(ds) == 2
        assert ds.examples[0].text == "hello"
        Path(fname).unlink()

    def test_custom_name(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"text": "x", "label": "y"}))
            fname = f.name
        ds = DatasetLoader.from_jsonl(fname, name="custom_name")
        assert ds.name == "custom_name"
        Path(fname).unlink()

    def test_with_metadata(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"text": "x", "label": "y", "metadata": {"src": "wiki"}}))
            fname = f.name
        ds = DatasetLoader.from_jsonl(fname)
        assert ds.examples[0].metadata == {"src": "wiki"}
        Path(fname).unlink()

    def test_skips_empty_lines(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"text": "a", "label": "x"}) + "\n\n")
            fname = f.name
        ds = DatasetLoader.from_jsonl(fname)
        assert len(ds) == 1
        Path(fname).unlink()


# ---------------------------------------------------------------------------
# from_prodigy
# ---------------------------------------------------------------------------


class TestFromProdigy:
    def test_basic_import(self) -> None:
        data = [
            {"text": "good product", "label": "positive"},
            {"text": "bad service", "label": "negative"},
        ]
        ds = from_prodigy(data, name="sentiment")
        assert len(ds) == 2
        assert ds.name == "sentiment"

    def test_answer_field_as_label(self) -> None:
        data = [{"text": "some text", "answer": "yes"}]
        ds = from_prodigy(data)
        assert ds.examples[0].label == "yes"

    def test_accept_normalised(self) -> None:
        data = [{"text": "good", "answer": "accept"}]
        ds = from_prodigy(data)
        assert ds.examples[0].label == "1"

    def test_reject_normalised(self) -> None:
        data = [{"text": "bad", "answer": "reject"}]
        ds = from_prodigy(data)
        assert ds.examples[0].label == "0"

    def test_extra_fields_in_metadata(self) -> None:
        data = [{"text": "x", "label": "pos", "annotator": "alice"}]
        ds = from_prodigy(data)
        assert ds.examples[0].metadata.get("annotator") == "alice"

    def test_empty_input(self) -> None:
        ds = from_prodigy([])
        assert len(ds) == 0

    def test_default_name(self) -> None:
        ds = from_prodigy([{"text": "x", "label": "y"}])
        assert ds.name == "prodigy"
