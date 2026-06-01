"""Delta Lake table loader for versioned training datasets.

:class:`DeltaTableLoader` reads a versioned Delta Lake table and returns a
:class:`~llm_agents.training.datasets.Dataset`.

The ``deltalake`` Python package (delta-rs, pure Python — no Spark) is
required.  All imports are deferred to :meth:`DeltaTableLoader.load` so the
module is importable without the ``delta-lake`` extra installed.

Usage::

    from llm_agents.training.datasets import DeltaTableLoader

    # Load the latest version
    dataset = DeltaTableLoader.load("/data/my_delta_table")

    # Load a specific historic version
    dataset = DeltaTableLoader.load(
        "/data/my_delta_table",
        version=3,
        text_column="utterance",
        label_column="intent",
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_agents.training.datasets._dataset import Dataset, Example


class DeltaTableLoader:
    """Load versioned Delta Lake tables as :class:`Dataset` objects.

    All methods are static; no instance state is required.

    The Delta table must contain at least a *text column* and a *label column*
    (default names ``"text"`` and ``"label"``).  All other columns are stored
    in :attr:`~llm_agents.training.datasets.Example.metadata`.
    """

    @staticmethod
    def load(
        table_path: str,
        *,
        version: int | None = None,
        text_column: str = "text",
        label_column: str = "label",
        name: str | None = None,
    ) -> Dataset:
        """Load a Delta Lake table as a :class:`Dataset`.

        Args:
            table_path:   Local path or URI of the Delta table directory.
            version:      Integer version to load.  When ``None`` the latest
                          version is used.
            text_column:  Name of the column containing the input text.
            label_column: Name of the column containing the target label.
            name:         Dataset name.  Defaults to the last component of
                          *table_path*.

        Returns:
            :class:`Dataset` with one :class:`Example` per table row.

        Raises:
            ImportError: If the ``deltalake`` package is not installed.
            KeyError:    If *text_column* or *label_column* is absent from the
                         table schema.
        """
        try:
            from deltalake import DeltaTable  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "deltalake is required for DeltaTableLoader. "
                "Install it with: pip install 'llm-agents-system[delta-lake]'"
            ) from exc

        dt_kwargs: dict[str, Any] = {}
        if version is not None:
            dt_kwargs["version"] = version

        dt = DeltaTable(table_path, **dt_kwargs)
        rows: list[dict[str, Any]] = dt.to_pyarrow_table().to_pylist()

        skip = {text_column, label_column}
        examples = [
            Example(
                text=str(row[text_column]),
                label=str(row[label_column]),
                metadata={k: v for k, v in row.items() if k not in skip},
            )
            for row in rows
        ]

        ds_name = name if name is not None else Path(table_path).name
        return Dataset(name=ds_name, examples=examples)
