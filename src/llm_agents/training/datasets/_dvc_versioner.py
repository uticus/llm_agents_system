"""DVC-backed dataset versioner.

:class:`DvcDataVersioner` wraps the ``dvc`` command-line tool via
:mod:`subprocess`, providing a Python API for tracking dataset files,
pushing/pulling to remote storage, and querying pipeline status.

``dvc`` is invoked as an external process — no Python import of the DVC
library is needed.  The ``tracking`` optional extra must be installed
(``pip install 'llm-agents-system[tracking]'``) for ``dvc`` to be on
``PATH``.

Usage::

    from llm_agents.training.datasets import DvcDataVersioner

    dvc = DvcDataVersioner(repo_path="/my/project")
    dvc.add("data/train.jsonl")        # dvc add data/train.jsonl
    dvc.push()                         # dvc push
    status = dvc.status()              # dvc status --json -> dict
"""

from __future__ import annotations

import json
import subprocess
from typing import Any


class DvcDataVersioner:
    """Wrap DVC CLI commands with a Python API.

    All operations are executed as subprocess calls to the ``dvc`` executable.
    A :exc:`RuntimeError` is raised if DVC is not installed or not on
    ``PATH``.

    Args:
        repo_path: Path to the DVC-initialised repository root.  Defaults to
                   the current working directory (``"."``).
        dvc_bin:   Name or path of the DVC executable.  Defaults to ``"dvc"``.
    """

    def __init__(
        self,
        repo_path: str = ".",
        dvc_bin: str = "dvc",
    ) -> None:
        self._repo_path = repo_path
        self._dvc_bin = dvc_bin

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, path: str) -> None:
        """Track a file or directory with DVC (``dvc add <path>``).

        Args:
            path: Path to the data file or directory to track, relative to
                  :attr:`repo_path`.
        """
        self._run([self._dvc_bin, "add", path])

    def push(self, remote: str | None = None) -> None:
        """Push tracked data to remote storage (``dvc push``).

        Args:
            remote: Name of the DVC remote to push to.  When ``None`` the
                    default remote is used.
        """
        cmd = [self._dvc_bin, "push"]
        if remote is not None:
            cmd += ["--remote", remote]
        self._run(cmd)

    def pull(
        self,
        path: str | None = None,
        remote: str | None = None,
    ) -> None:
        """Pull tracked data from remote storage (``dvc pull``).

        Args:
            path:   Specific file or stage to pull.  When ``None`` all tracked
                    data is pulled.
            remote: Name of the DVC remote to pull from.  When ``None`` the
                    default remote is used.
        """
        cmd = [self._dvc_bin, "pull"]
        if path is not None:
            cmd.append(path)
        if remote is not None:
            cmd += ["--remote", remote]
        self._run(cmd)

    def status(self) -> dict[str, Any]:
        """Return the DVC pipeline/data status as a dict.

        Runs ``dvc status --json`` and parses the JSON output.  Returns an
        empty dict when the workspace is up-to-date (no output) or when DVC
        reports an empty status.

        Returns:
            Parsed JSON dict.  Keys are stage/file names; values describe
            pending changes.  Returns ``{}`` for a clean workspace.
        """
        result = self._run(
            [self._dvc_bin, "status", "--json"],
            capture_output=True,
        )
        raw = (result.stdout or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
        return parsed if isinstance(parsed, dict) else {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(
        self,
        cmd: list[str],
        *,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess:
        """Execute *cmd* in :attr:`repo_path`; raise on non-zero exit."""
        try:
            return subprocess.run(
                cmd,
                cwd=self._repo_path,
                check=True,
                capture_output=capture_output,
                text=capture_output,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"DVC executable not found ({self._dvc_bin!r}). "
                "Install it with: pip install 'llm-agents-system[tracking]'"
            ) from exc
