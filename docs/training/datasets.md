# training/datasets

## Overview

The `training/datasets` module provides the data layer for training pipelines in the llm_agents_system platform. It models annotated training data as in-memory collections of (text, label) pairs, supports loading from multiple sources (in-memory lists, JSONL files, Prodigy annotation exports, versioned Delta Lake tables), provides deterministic train/validation splitting, runs basic schema and label-distribution validation, and computes a content-based version hash that enables downstream systems to detect dataset changes without comparing full contents. The module is designed to be lightweight: its core types (`Dataset`, `Example`, `DatasetLoader`, `from_prodigy`) import cleanly with no optional extras. Heavy storage integrations (`DeltaTableLoader` via `delta-lake` extra, `DvcDataVersioner` via `tracking` extra) are deferred to optional extras that do not affect the base import.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `Example` | dataclass | A single annotated (text, label) training example with optional metadata. |
| `Dataset` | dataclass | In-memory collection of `Example` objects with split, validate, and version. |
| `DatasetLoader` | class | Static factory methods for loading datasets from various sources. |
| `from_prodigy` | function | Import a Prodigy annotation export list into a `Dataset`. |
| `DeltaTableLoader` | class | Load versioned Delta Lake tables as `Dataset` objects (requires `delta-lake` extra). |
| `DvcDataVersioner` | class | DVC CLI wrapper for dataset file versioning (requires `tracking` extra). |

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

### DeltaTableLoader

```
DeltaTableLoader.load(
    table_path: str,
    *,
    version: int | None = None,   # Delta table version; None = latest
    text_column: str = "text",    # column to use as Example.text
    label_column: str = "label",  # column to use as Example.label
    name: str | None = None,      # dataset name; default = last path component
) -> Dataset
```

Requires `deltalake` package: `pip install 'llm-agents-system[delta-lake]'`.

Reads the Delta Lake table at `table_path` using the pure-Python `delta-rs` driver (no Spark required). If `version` is provided, the table is read at that specific version; otherwise the latest snapshot is used. Every row is mapped to an `Example`: `text_column` and `label_column` values are coerced to `str`; all remaining columns are stored in `Example.metadata`. Extra columns (`text_column`, `label_column`) are excluded from `metadata`.

`ImportError` is raised with an actionable message if `deltalake` is not installed.

### DvcDataVersioner

```
DvcDataVersioner(
    repo_path: str = ".",    # path to the Git/DVC repository root
    dvc_bin: str = "dvc",    # DVC executable (full path or name on PATH)
)

add(path: str) -> None
    # Runs: dvc add <path>
    # Starts tracking a file or directory with DVC.

push(remote: str | None = None) -> None
    # Runs: dvc push [--remote <remote>]
    # Uploads tracked data to the remote storage.

pull(
    path: str | None = None,
    remote: str | None = None,
) -> None
    # Runs: dvc pull [<path>] [--remote <remote>]
    # Downloads tracked data from remote storage.

status() -> dict[str, Any]
    # Runs: dvc status --json
    # Returns parsed JSON status dict. Empty dict if no changes.
    # Returns {"raw": "<output>"} if DVC output is not valid JSON.
```

Requires DVC installed and accessible via `dvc_bin`: `pip install 'llm-agents-system[tracking]'`.

All commands are run via `subprocess.run(check=True, cwd=repo_path)`. If `dvc_bin` is not found on PATH, `RuntimeError` is raised with an actionable message that mentions DVC installation. `subprocess.CalledProcessError` propagates unchanged if DVC exits with a non-zero code.

---

## Architecture

### Conceptual view

```
  Source:                  DatasetLoader          from_prodigy()     DeltaTableLoader
  - list[tuple]   ------>  .from_examples()  \                          .load()
  - JSONL file    ------>  .from_jsonl()      +-->  Dataset  <-----------/
  - Prodigy JSON  ----------------------------/      |
                                                     |
                                              .split()  .validate()
                                              /               \
                                    (train, val)         list[str]
                                    Datasets             (issues)

  File versioning:
  DvcDataVersioner --[subprocess]--> dvc CLI  <-->  remote storage
```

### Data flow

**Loading via DatasetLoader**:
1. `from_examples(name, [(text, label), ...])` wraps each tuple into an `Example` and constructs a `Dataset`. `__post_init__` computes the content hash.
2. `from_jsonl(path)` reads the file line by line, parses each JSON object, extracts `"text"` and `"label"`, and optionally preserves `"metadata"`. Constructs a `Dataset` the same way.

**Prodigy import**:
1. `from_prodigy(data)` iterates over annotation dicts. For each, extracts `"text"` and `"label"` (with `"answer"` as fallback). Normalises `"accept"` -> `"1"` and `"reject"` -> `"0"`. Collects remaining keys into `metadata`.

**Delta Lake loading**:
1. `DeltaTableLoader.load(table_path, version=version)` lazily imports `deltalake.DeltaTable`. Constructs the table object with an optional `version` kwarg.
2. Calls `dt.to_pyarrow_table().to_pylist()` to obtain a list of row dicts.
3. Maps each row dict to an `Example`: `str(row[text_column])` → `text`, `str(row[label_column])` → `label`, remaining keys → `metadata`.
4. Constructs and returns a `Dataset` named after the last path component (or the explicit `name` argument).

**DVC versioning**:
1. `DvcDataVersioner._run(cmd)` wraps `subprocess.run(cmd, cwd=repo_path, check=True)`. Translates `FileNotFoundError` (DVC binary missing) into `RuntimeError`; lets `CalledProcessError` propagate.
2. `add(path)` runs `dvc add <path>` — creates a `.dvc` tracking file.
3. `push(remote)` runs `dvc push [--remote <remote>]` — uploads data to remote.
4. `pull(path, remote)` runs `dvc pull [<path>] [--remote <remote>]` — downloads data.
5. `status()` runs `dvc status --json`, parses stdout as JSON, falls back to `{"raw": ...}` on parse failure.

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

**DeltaTableLoader** mirrors this pattern with a single `@staticmethod load()` method. The class serves as a namespace; there is no per-instance state because all configuration (path, version, column names) is passed per-call.

**Prodigy normalisation**: the `from_prodigy` function handles the common Prodigy binary annotation convention where `"accept"` and `"reject"` are the answer values. Normalising these to `"1"` and `"0"` ensures downstream training code does not need to know about Prodigy-specific conventions.

**DvcDataVersioner wraps the CLI**: DVC's primary interface is its command-line tool. Wrapping the CLI via `subprocess` avoids the heavy DVC Python API import and keeps the integration shallow. The subprocess model also matches how DVC is typically used in CI/CD pipelines.

---

## Design decisions and tradeoffs

- **Decision**: `split` uses text-sort for deterministic shuffling rather than a seeded random number generator. **Why**: Avoids requiring callers to manage random seeds and makes the split reproducible across Python versions without depending on `random` module state. **Tradeoff**: The resulting "shuffle" is a sort, not a true randomisation; correlated examples with similar text may end up in the same split, producing biased train/val distributions.

- **Decision**: `version` is an MD5 hash computed from text and label content only (not metadata). **Why**: Metadata often contains provenance information (annotator ID, timestamp) that changes without changing the actual training content. Using only text and label ensures that adding or changing metadata does not invalidate the version unnecessarily. **Tradeoff**: Two datasets with the same text/label content but different metadata will have identical version hashes, which may be surprising if metadata carries semantic meaning.

- **Decision**: `validate` returns a list of issues rather than raising an exception. **Why**: Callers often want to inspect all issues at once rather than fixing them one at a time. Raising on the first error would require re-running validation after each fix. **Tradeoff**: Callers must remember to check the return value; a dataset with issues can still be used without triggering any error.

- **Decision**: `from_jsonl` reads the entire file into memory via `path.read_text()`. **Why**: Simplicity; the module targets training datasets that are typically small enough to fit in memory (thousands to low millions of examples). **Tradeoff**: Very large JSONL files (hundreds of millions of examples) cannot be loaded this way; streaming loading would be required.

- **Decision**: `DeltaTableLoader` uses `to_pyarrow_table().to_pylist()` rather than iterating the table in streaming fashion. **Why**: Keeps the implementation simple and avoids additional pyarrow streaming API complexity. For the target use case (training datasets that fit in memory), loading the full table at once is appropriate. **Tradeoff**: Very large Delta tables (hundreds of millions of rows) will exhaust memory; streaming or batching would be required for such scales.

- **Decision**: `DeltaTableLoader` coerces `text_column` and `label_column` values to `str` regardless of the column's actual dtype. **Why**: `Example.text` and `Example.label` are always `str`. Delta tables may store these as integers or other types (e.g., label encoded as int). Coercion ensures the `Dataset` invariant is maintained without requiring callers to pre-process the schema. **Tradeoff**: Numeric text values (e.g., `42`) produce the string `"42"`, which may not be meaningful in all contexts.

- **Decision**: `DvcDataVersioner` translates `FileNotFoundError` to `RuntimeError` but lets `subprocess.CalledProcessError` propagate unchanged. **Why**: `FileNotFoundError` means DVC is not installed — an environment issue the caller needs actionable guidance on. `CalledProcessError` means DVC ran but exited non-zero — a DVC-level error with its own stderr output that the caller may want to inspect or re-raise with additional context. **Tradeoff**: The two error types require different handling at the call site; callers that want uniform error handling must catch both.

---

## Scaling concerns

The module is in-memory only. All examples are held as Python objects in a list. For typical fine-tuning datasets (10K to 500K examples with short texts), memory usage is acceptable (roughly 200-500 bytes per example overhead). Beyond a few million examples, in-memory storage becomes impractical.

`_content_hash` serialises the entire example list to JSON before hashing, which is O(n) in time and memory. For very large datasets this hash computation at construction time may add noticeable overhead.

`split` copies the example list, temporarily doubling memory usage during the split operation.

`DeltaTableLoader.load` loads the entire table into memory. Memory usage is the product of row count and average row size. For tables with wide schemas, the extra columns stored in `Example.metadata` contribute to memory consumption.

`DvcDataVersioner` delegates all storage and transfer to the DVC + remote stack. Throughput is bounded by DVC's transfer speed and the remote's bandwidth; the Python wrapper adds no bottleneck.

**What breaks first**: memory, for very large datasets. The version hash computation is the second concern.

---

## Future improvements

- **Streaming JSONL loading**: add a `DatasetLoader.stream_jsonl(path)` generator that yields `Example` objects one at a time, avoiding the full in-memory load for large files.
- **Random shuffle with seed**: replace the text-sort shuffle with a seeded `random.shuffle` that accepts an explicit `seed` parameter, providing genuine randomisation with reproducibility.
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

Loading a versioned Delta Lake table:

```python
# requires: uv sync --extra delta-lake
from llm_agents.training.datasets import DeltaTableLoader

# Load latest snapshot
ds = DeltaTableLoader.load("/data/delta/intent_dataset")
print(len(ds), ds.name)   # ds.name = "intent_dataset"

# Load a specific historical version
ds_v3 = DeltaTableLoader.load(
    "/data/delta/intent_dataset",
    version=3,
    name="intent-v3",
)

# Custom column names
ds = DeltaTableLoader.load(
    "/data/delta/chat_labels",
    text_column="utterance",
    label_column="intent",
)
print(ds.examples[0].text)    # value from "utterance" column
print(ds.examples[0].label)   # value from "intent" column
# Other columns end up in metadata:
print(ds.examples[0].metadata)  # {"source": "prod", "score": 0.97, ...}
```

Tracking dataset files with DVC:

```python
# requires: uv sync --extra tracking  (also needs: dvc init in repo root)
from llm_agents.training.datasets import DvcDataVersioner

dvc = DvcDataVersioner(repo_path="/my/project", dvc_bin="dvc")

# Stage a new dataset file for DVC tracking
dvc.add("data/train.jsonl")        # creates data/train.jsonl.dvc

# Push to remote storage (DVC remote must be configured in .dvc/config)
dvc.push(remote="my-s3")

# Pull a specific file from remote on another machine
dvc.pull(path="data/train.jsonl", remote="my-s3")

# Check status of all tracked files
status = dvc.status()
print(status)  # {"data/train.jsonl": ["modified"]} or {}
```

End-to-end: load Delta Lake dataset, validate, split, and fine-tune:

```python
# requires: uv sync --extra training --extra delta-lake
from llm_agents.training.datasets import DeltaTableLoader
from llm_agents.training.fine_tuning import FineTuneConfig, FineTuner
from llm_agents.training.experiment_tracking import MLflowTracker

ds = DeltaTableLoader.load("/data/delta/classification", version=7)
issues = ds.validate()
if issues:
    raise ValueError(f"Dataset issues: {issues}")

train, val = ds.split(train_ratio=0.85)

config = FineTuneConfig(
    base_model="distilgpt2",
    output_dir="/checkpoints/clf-run",
    num_epochs=2,
    lora_r=8,
    lora_alpha=16,
)
tracker = MLflowTracker(
    tracking_uri="http://mlflow.internal:5000",
    experiment_name="classification-finetune",
)
tuner = FineTuner(config=config, tracker=tracker)
result = tuner.run(dataset=train)
print(result.model_path, result.metrics)
```
