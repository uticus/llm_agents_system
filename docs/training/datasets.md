# training/datasets

## Overview

The `training/datasets` module provides the data layer for training pipelines in the llm_agents_system platform. It models annotated training data as in-memory collections of (text, label) pairs, supports loading from multiple sources (in-memory lists, JSONL files, Prodigy annotation exports), provides deterministic train/validation splitting, runs basic schema and label-distribution validation, and computes a content-based version hash that enables downstream systems to detect dataset changes without comparing full contents. The module is designed to be lightweight: it imports cleanly with no optional extras, keeping it usable in data-preparation scripts that do not need a full training environment. Heavy storage integrations (Delta Lake, DVC) are explicitly deferred to optional extras not yet implemented.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `Example` | dataclass | A single annotated (text, label) training example with optional metadata. |
| `Dataset` | dataclass | In-memory collection of `Example` objects with split, validate, and version. |
| `DatasetLoader` | class | Static factory methods for loading datasets from various sources. |
| `from_prodigy` | function | Import a Prodigy annotation export list into a `Dataset`. |

### Example

```
Example(
    text: str,
    label: str,
    metadata: dict[str, Any] = {},
)
```

### Dataset

```
Dataset(
    name: str,
    examples: list[Example] = [],
    version: str = "",   # auto-computed MD5 hash if not supplied
)

split(
    train_ratio: float = 0.8,
    *,
    shuffle: bool = False,
) -> tuple[Dataset, Dataset]      # (train_dataset, val_dataset)

validate() -> list[str]           # returns list of warning/error strings; empty = OK

__len__() -> int
```

`version` is computed at `__post_init__` time as an MD5 hash of `name + serialised examples`. If `version` is provided explicitly it is used as-is.

### DatasetLoader

```
DatasetLoader.from_examples(
    name: str,
    examples: list[tuple[str, str]],
) -> Dataset

DatasetLoader.from_jsonl(
    path: str | Path,
    *,
    name: str | None = None,
) -> Dataset
```

`from_jsonl` expects one JSON object per line with `"text"` and `"label"` keys. An optional `"metadata"` key is preserved.

### from_prodigy

```
from_prodigy(
    data: list[dict[str, Any]],
    *,
    name: str = "prodigy",
) -> Dataset
```

Accepts the parsed list of annotation dicts from a Prodigy JSONL export. Normalises `"accept"` to `"1"` and `"reject"` to `"0"`. Uses `"label"` if present, falls back to `"answer"`.

---

## Architecture

### Conceptual view

```
  Source:                  DatasetLoader          from_prodigy()
  - list[tuple]   ------>  .from_examples()  \
  - JSONL file    ------>  .from_jsonl()      +-->  Dataset
  - Prodigy JSON  ----------------------------/      |
                                                     |
                                              .split()  .validate()
                                              /               \
                                    (train, val)         list[str]
                                    Datasets             (issues)
```

### Data flow

**Loading via DatasetLoader**:
1. `from_examples(name, [(text, label), ...])` wraps each tuple into an `Example` and constructs a `Dataset`. `__post_init__` computes the content hash.
2. `from_jsonl(path)` reads the file line by line, parses each JSON object, extracts `"text"` and `"label"`, and optionally preserves `"metadata"`. Constructs a `Dataset` the same way.

**Prodigy import**:
1. `from_prodigy(data)` iterates over annotation dicts. For each, extracts `"text"` and `"label"` (with `"answer"` as fallback). Normalises `"accept"` -> `"1"` and `"reject"` -> `"0"`. Collects remaining keys into `metadata`.

**Splitting**:
1. `dataset.split(train_ratio, shuffle=False)` copies the example list. If `shuffle=True`, sorts by `text` string (deterministic, not random). Computes split index `n = max(1, int(len * train_ratio))`. Returns two new `Dataset` objects named `"{name}_train"` and `"{name}_val"`.

**Validation**:
1. `dataset.validate()` checks for empty text or label in each example and for single-label datasets (which indicate a data preparation error). Returns all issues as strings; empty list means the dataset is valid.

**Version hashing**:
1. `_content_hash(name, examples)` serialises `name` concatenated with a JSON array of `[{"text": ..., "label": ...}]` dicts (sorted keys), and returns the MD5 hex digest. `usedforsecurity=False` is passed to suppress security warnings on platforms that flag MD5 usage.

### Key abstractions

**Example** is deliberately minimal: just text, label, and arbitrary metadata. It does not enforce label types (categorical, continuous, multi-label) because the module is intended to serve multiple task types. The `label` field is always a `str`, which is the lowest common denominator across classification, generation, and ranking tasks.

**Dataset** owns the version hash but does not enforce immutability. If the `examples` list is mutated after construction, the `version` field becomes stale. Callers are responsible for not mutating dataset contents after construction.

**DatasetLoader** uses `@staticmethod` methods rather than a class with instance state. There is no configuration state that would justify instantiation. This makes the loading API feel functional and avoids requiring callers to construct a loader object before loading data.

**Prodigy normalisation**: the `from_prodigy` function handles the common Prodigy binary annotation convention where `"accept"` and `"reject"` are the answer values. Normalising these to `"1"` and `"0"` ensures downstream training code does not need to know about Prodigy-specific conventions.

---

## Design decisions and tradeoffs

- **Decision**: `split` uses text-sort for deterministic shuffling rather than a seeded random number generator. **Why**: Avoids requiring callers to manage random seeds and makes the split reproducible across Python versions without depending on `random` module state. **Tradeoff**: The resulting "shuffle" is a sort, not a true randomisation; correlated examples with similar text may end up in the same split, producing biased train/val distributions.

- **Decision**: `version` is an MD5 hash computed from text and label content only (not metadata). **Why**: Metadata often contains provenance information (annotator ID, timestamp) that changes without changing the actual training content. Using only text and label ensures that adding or changing metadata does not invalidate the version unnecessarily. **Tradeoff**: Two datasets with the same text/label content but different metadata will have identical version hashes, which may be surprising if metadata carries semantic meaning.

- **Decision**: `validate` returns a list of issues rather than raising an exception. **Why**: Callers often want to inspect all issues at once rather than fixing them one at a time. Raising on the first error would require re-running validation after each fix. **Tradeoff**: Callers must remember to check the return value; a dataset with issues can still be used without triggering any error.

- **Decision**: `from_jsonl` reads the entire file into memory via `path.read_text()`. **Why**: Simplicity; the module targets training datasets that are typically small enough to fit in memory (thousands to low millions of examples). **Tradeoff**: Very large JSONL files (hundreds of millions of examples) cannot be loaded this way; streaming loading would be required.

- **Decision**: Heavy storage backends (Delta Lake, DVC) are explicitly called out in the module docstring as deferred. **Why**: Keeping the core module import-clean enables use in data preparation scripts without installing a large ML dependency stack. **Tradeoff**: The module cannot currently load data from Delta Lake or DVC natively; callers must pre-load data and pass it to `from_examples`.

---

## Scaling concerns

The module is in-memory only. All examples are held as Python objects in a list. For typical fine-tuning datasets (10K to 500K examples with short texts), memory usage is acceptable (roughly 200-500 bytes per example overhead). Beyond a few million examples, in-memory storage becomes impractical.

`_content_hash` serialises the entire example list to JSON before hashing, which is O(n) in time and memory. For very large datasets this hash computation at construction time may add noticeable overhead.

`split` copies the example list, temporarily doubling memory usage during the split operation.

**What breaks first**: memory, for very large datasets. The version hash computation is the second concern.

---

## Future improvements

- **Streaming JSONL loading**: add a `DatasetLoader.stream_jsonl(path)` generator that yields `Example` objects one at a time, avoiding the full in-memory load for large files.
- **Random shuffle with seed**: replace the text-sort shuffle with a seeded `random.shuffle` that accepts an explicit `seed` parameter, providing genuine randomisation with reproducibility.
- **Delta Lake / DVC loading**: implement the deferred `DatasetLoader.from_delta(path)` and `DatasetLoader.from_dvc(path)` methods behind the `training` extra.
- **Label distribution statistics**: extend `validate` (or add a `statistics()` method) to return label counts, class imbalance ratios, and mean text length as part of dataset quality reporting.
- **HuggingFace Datasets bridge**: add a `DatasetLoader.from_hf_dataset(hf_dataset)` method that converts a HuggingFace `datasets.Dataset` object into a `Dataset`, enabling use of the HuggingFace hub as a data source.

---

## Usage examples

Loading from in-memory pairs:

```python
from llm_agents.training.datasets import DatasetLoader

ds = DatasetLoader.from_examples(
    name="sentiment",
    examples=[
        ("I love this product", "positive"),
        ("This is terrible", "negative"),
        ("It is okay", "neutral"),
    ],
)
print(len(ds), ds.version)
```

Loading from JSONL and splitting:

```python
from llm_agents.training.datasets import DatasetLoader

ds = DatasetLoader.from_jsonl("/data/training.jsonl", name="intent")
issues = ds.validate()
if issues:
    print("Validation issues:", issues)

train, val = ds.split(train_ratio=0.8, shuffle=True)
print(len(train), len(val))
```

Importing from Prodigy:

```python
import json
from llm_agents.training.datasets import from_prodigy

raw_annotations = json.loads(Path("/exports/annotations.jsonl").read_text())
ds = from_prodigy(raw_annotations, name="ner_export")
print(ds.name, len(ds))
```
