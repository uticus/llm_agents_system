"""Dataset model, DatasetLoader, and Prodigy import helper.

The Dataset model is a simple in-memory collection of (text, label) examples.
Heavy dependencies (Delta Lake, DVC) are deferred; this module imports cleanly
without the ``training`` extra.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Core data model
# ---------------------------------------------------------------------------


@dataclass
class Example:
    """A single annotated training example.

    Args:
        text:    Input text.
        label:   Target label or output string.
        metadata: Arbitrary key-value metadata (source, annotator, etc.).
    """

    text: str
    label: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Dataset:
    """An in-memory collection of annotated training examples.

    Args:
        name:     Human-readable dataset name.
        examples: List of :class:`Example` objects.
        version:  Content-based version hash (computed automatically when
                  not supplied).

    Attributes:
        version: MD5 content hash of ``name + serialised examples``.
    """

    name: str
    examples: list[Example] = field(default_factory=list)
    version: str = ""

    def __post_init__(self) -> None:
        if not self.version:
            self.version = _content_hash(self.name, self.examples)

    # ------------------------------------------------------------------
    # Splits
    # ------------------------------------------------------------------

    def split(
        self,
        train_ratio: float = 0.8,
        *,
        shuffle: bool = False,
    ) -> tuple[Dataset, Dataset]:
        """Return (train, val) sub-datasets with no overlap.

        Args:
            train_ratio: Fraction of examples assigned to the training split
                         (default 0.8).  The validation split receives the
                         remaining examples.
            shuffle:     When ``True`` shuffle examples before splitting
                         (deterministic: uses Python's built-in sort on text).

        Returns:
            Tuple of ``(train_dataset, val_dataset)``.
        """
        examples = list(self.examples)
        if shuffle:
            examples = sorted(examples, key=lambda e: e.text)
        n = max(1, int(len(examples) * train_ratio))
        train_ex = examples[:n]
        val_ex = examples[n:]
        return (
            Dataset(name=f"{self.name}_train", examples=train_ex),
            Dataset(name=f"{self.name}_val", examples=val_ex),
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Run basic schema and label-distribution checks.

        Returns:
            List of human-readable warning/error strings.  Empty list = OK.
        """
        issues: list[str] = []
        if not self.examples:
            issues.append("Dataset is empty.")
            return issues
        label_counts: dict[str, int] = {}
        for i, ex in enumerate(self.examples):
            if not ex.text.strip():
                issues.append(f"Example {i} has empty text.")
            if not ex.label.strip():
                issues.append(f"Example {i} has empty label.")
            label_counts[ex.label] = label_counts.get(ex.label, 0) + 1
        if len(label_counts) == 1:
            issues.append(f"Only one unique label present: '{next(iter(label_counts))}'.")
        return issues

    def __len__(self) -> int:
        return len(self.examples)


# ---------------------------------------------------------------------------
# DatasetLoader
# ---------------------------------------------------------------------------


class DatasetLoader:
    """Load a :class:`Dataset` from various formats.

    All heavy dependencies (Delta, DVC) are behind optional extras; this
    class provides in-memory and JSON-file loading without any extras.
    """

    @staticmethod
    def from_examples(
        name: str,
        examples: list[tuple[str, str]],
    ) -> Dataset:
        """Create a dataset from a plain list of (text, label) tuples.

        Args:
            name:     Dataset name.
            examples: List of ``(text, label)`` pairs.

        Returns:
            :class:`Dataset` with one :class:`Example` per pair.
        """
        return Dataset(
            name=name,
            examples=[Example(text=t, label=lbl) for t, lbl in examples],
        )

    @staticmethod
    def from_jsonl(path: str | Path, *, name: str | None = None) -> Dataset:
        """Load a dataset from a JSONL file.

        Each line must be a JSON object with ``"text"`` and ``"label"`` keys.
        An optional ``"metadata"`` key may carry additional key-value data.

        Args:
            path: Path to the JSONL file.
            name: Dataset name.  Defaults to the file stem.

        Returns:
            :class:`Dataset` loaded from the file.
        """
        path = Path(path)
        ds_name = name or path.stem
        examples: list[Example] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            examples.append(
                Example(
                    text=obj["text"],
                    label=obj["label"],
                    metadata=obj.get("metadata", {}),
                )
            )
        return Dataset(name=ds_name, examples=examples)


# ---------------------------------------------------------------------------
# Prodigy import
# ---------------------------------------------------------------------------


def from_prodigy(data: list[dict[str, Any]], *, name: str = "prodigy") -> Dataset:
    """Import a Prodigy annotation export into a :class:`Dataset`.

    Prodigy exports annotations as JSONL files (one JSON object per line).
    This function accepts the already-parsed list of annotation dicts.

    Expected fields per annotation:
    - ``"text"`` (required): The annotated text.
    - ``"label"`` / ``"answer"`` (required): The annotation result.
      ``"accept"`` is normalised to ``"1"``; ``"reject"`` to ``"0"``.

    Args:
        data: List of annotation dicts from a Prodigy export.
        name: Dataset name.

    Returns:
        :class:`Dataset` with one example per accepted/rejected annotation.
    """
    examples: list[Example] = []
    for ann in data:
        text = ann.get("text", "")
        label = ann.get("label", ann.get("answer", ""))
        # Normalise Prodigy binary answers
        if label == "accept":
            label = "1"
        elif label == "reject":
            label = "0"
        meta = {k: v for k, v in ann.items() if k not in {"text", "label", "answer"}}
        examples.append(Example(text=text, label=str(label), metadata=meta))
    return Dataset(name=name, examples=examples)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_hash(name: str, examples: list[Example]) -> str:
    payload = name + json.dumps(
        [{"text": e.text, "label": e.label} for e in examples],
        sort_keys=True,
    )
    return hashlib.md5(payload.encode(), usedforsecurity=False).hexdigest()
