"""Unit tests for DvcDataVersioner.

``subprocess.run`` is patched throughout; no real DVC installation is needed.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from llm_agents.training.datasets import DvcDataVersioner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_run(returncode: int = 0, stdout: str = "") -> MagicMock:
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    return result


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestDvcVersionerInit:
    def test_repo_path_stored(self) -> None:
        d = DvcDataVersioner(repo_path="/my/project")
        assert d._repo_path == "/my/project"

    def test_dvc_bin_stored(self) -> None:
        d = DvcDataVersioner(dvc_bin="/usr/local/bin/dvc")
        assert d._dvc_bin == "/usr/local/bin/dvc"

    def test_defaults(self) -> None:
        d = DvcDataVersioner()
        assert d._repo_path == "."
        assert d._dvc_bin == "dvc"


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------


class TestDvcVersionerAdd:
    def test_add_calls_subprocess_run(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.add("data/train.jsonl")
        mock_run.assert_called_once()

    def test_add_command_includes_path(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.add("data/train.jsonl")
        args, _ = mock_run.call_args
        assert "data/train.jsonl" in args[0]

    def test_add_command_starts_with_dvc_add(self) -> None:
        d = DvcDataVersioner(dvc_bin="dvc")
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.add("data/file.csv")
        args, _ = mock_run.call_args
        assert args[0][:2] == ["dvc", "add"]

    def test_add_uses_repo_path_as_cwd(self) -> None:
        d = DvcDataVersioner(repo_path="/my/repo")
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.add("data/file.csv")
        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == "/my/repo"

    def test_add_uses_custom_dvc_bin(self) -> None:
        d = DvcDataVersioner(dvc_bin="/custom/dvc")
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.add("file.csv")
        args, _ = mock_run.call_args
        assert args[0][0] == "/custom/dvc"


# ---------------------------------------------------------------------------
# push()
# ---------------------------------------------------------------------------


class TestDvcVersionerPush:
    def test_push_without_remote(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.push()
        args, _ = mock_run.call_args
        assert args[0] == ["dvc", "push"]

    def test_push_with_remote(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.push(remote="my-s3")
        args, _ = mock_run.call_args
        assert "--remote" in args[0]
        assert "my-s3" in args[0]

    def test_push_check_true(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.push()
        _, kwargs = mock_run.call_args
        assert kwargs["check"] is True


# ---------------------------------------------------------------------------
# pull()
# ---------------------------------------------------------------------------


class TestDvcVersionerPull:
    def test_pull_without_args(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.pull()
        args, _ = mock_run.call_args
        assert args[0] == ["dvc", "pull"]

    def test_pull_with_path(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.pull(path="data/train.jsonl")
        args, _ = mock_run.call_args
        assert "data/train.jsonl" in args[0]

    def test_pull_with_remote(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.pull(remote="s3-remote")
        args, _ = mock_run.call_args
        assert "--remote" in args[0]
        assert "s3-remote" in args[0]

    def test_pull_with_path_and_remote(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            d.pull(path="data/train.csv", remote="myremote")
        args, _ = mock_run.call_args
        cmd = args[0]
        assert "data/train.csv" in cmd
        assert "--remote" in cmd
        assert "myremote" in cmd


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------


class TestDvcVersionerStatus:
    def test_status_returns_dict(self) -> None:
        payload = json.dumps({"data/train.jsonl": ["modified"]})
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run(stdout=payload)):
            result = d.status()
        assert isinstance(result, dict)

    def test_status_parses_json(self) -> None:
        payload = json.dumps({"stage1": ["changed"]})
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run(stdout=payload)):
            result = d.status()
        assert result == {"stage1": ["changed"]}

    def test_status_empty_output_returns_empty_dict(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run(stdout="")):
            result = d.status()
        assert result == {}

    def test_status_invalid_json_returns_raw(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run(stdout="not-json")):
            result = d.status()
        assert "raw" in result

    def test_status_passes_json_flag(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", return_value=_mock_run(stdout="{}")) as mock_run:
            d.status()
        args, _ = mock_run.call_args
        assert "--json" in args[0]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestDvcVersionerErrors:
    def test_runtime_error_when_dvc_not_found(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", side_effect=FileNotFoundError("dvc not found")):
            with pytest.raises(RuntimeError, match="DVC executable not found"):
                d.add("data/file.csv")

    def test_called_process_error_propagates(self) -> None:
        d = DvcDataVersioner()
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "dvc"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                d.push()

    def test_error_message_mentions_tracking_extra(self) -> None:
        d = DvcDataVersioner()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="tracking"):
                d.add("file.csv")
