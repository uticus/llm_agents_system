"""Datasets: annotation (Prodigy) and storage (Delta Lake / DVC) for training data.

Requires the ``training`` extra.

Public surface
--------------
- :class:`Example` — a single (text, label) annotated training example.
- :class:`Dataset` — in-memory collection of examples with split + validate.
- :class:`DatasetLoader` — load from examples, JSONL file, or other sources.
- :func:`from_prodigy` — import Prodigy annotation exports.
- :class:`DvcDataVersioner` — DVC CLI wrapper for dataset file versioning
  (requires the ``tracking`` extra).
- :class:`DeltaTableLoader` — load versioned Delta Lake tables as
  :class:`Dataset` objects (requires the ``delta-lake`` extra).
"""

from llm_agents.training.datasets._dataset import (
    Dataset,
    DatasetLoader,
    Example,
    from_prodigy,
)
from llm_agents.training.datasets._delta_loader import DeltaTableLoader
from llm_agents.training.datasets._dvc_versioner import DvcDataVersioner

__all__ = [
    "Dataset",
    "DatasetLoader",
    "DeltaTableLoader",
    "DvcDataVersioner",
    "Example",
    "from_prodigy",
]
