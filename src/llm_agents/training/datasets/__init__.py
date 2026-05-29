"""Datasets: annotation (Prodigy) and storage (Delta Lake / DVC) for training data.

Requires the ``training`` extra.

Public surface
--------------
- :class:`Example` — a single (text, label) annotated training example.
- :class:`Dataset` — in-memory collection of examples with split + validate.
- :class:`DatasetLoader` — load from examples, JSONL file, or other sources.
- :func:`from_prodigy` — import Prodigy annotation exports.
"""

from llm_agents.training.datasets._dataset import (
    Dataset,
    DatasetLoader,
    Example,
    from_prodigy,
)

__all__ = [
    "Dataset",
    "DatasetLoader",
    "Example",
    "from_prodigy",
]
