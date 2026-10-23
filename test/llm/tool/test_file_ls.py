"LS: `.gitignore`, depth, and the summary view."

import os
import subprocess

import pytest

from zrb.llm.tool.file import list_files
from zrb.llm.tool.file_observation import clear_observed


@pytest.fixture(autouse=True)
def _reset_observed_state():
    clear_observed()
    yield
    clear_observed()


def _init_checkout(path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def _write(path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_list_files_hides_gitignored(tmp_path):
    """Generated trees (htmlcov, dist) must not bury the repository's shape."""
    _init_checkout(tmp_path)
    _write(tmp_path / ".gitignore", "ignored/\n")
    _write(tmp_path / "ignored" / "artifact.html")
    _write(tmp_path / "kept.txt")

    files = list_files(str(tmp_path)).get("files", [])

    assert "kept.txt" in files
    assert os.path.join("ignored", "artifact.html") not in files


def test_list_files_gitignore_false_lists_ignored(tmp_path):
    _init_checkout(tmp_path)
    _write(tmp_path / ".gitignore", "ignored/\n")
    _write(tmp_path / "ignored" / "artifact.html")

    files = list_files(str(tmp_path), gitignore=False).get("files", [])

    assert os.path.join("ignored", "artifact.html") in files


def test_list_files_outside_a_checkout_still_lists(tmp_path):
    """No repository above the directory: the git filter must not hide it all."""
    _write(tmp_path / "plain.txt")

    files = list_files(str(tmp_path)).get("files", [])

    assert "plain.txt" in files


def test_list_files_depth_limits_the_walk(tmp_path):
    _write(tmp_path / "root.txt")
    _write(tmp_path / "sub" / "one.txt")
    _write(tmp_path / "sub" / "deep" / "two.txt")

    shallow = list_files(str(tmp_path), depth=1).get("files", [])
    deeper = list_files(str(tmp_path), depth=2).get("files", [])

    assert "root.txt" in shallow
    assert os.path.join("sub", "one.txt") not in shallow
    assert os.path.join("sub", "one.txt") in deeper
    assert os.path.join("sub", "deep", "two.txt") not in deeper


def test_list_files_summary_counts_by_top_level(tmp_path):
    _write(tmp_path / "root.txt")
    _write(tmp_path / "sub" / "one.txt")
    _write(tmp_path / "sub" / "two.txt")

    result = list_files(str(tmp_path), summary=True)

    assert result["total_files"] == 3
    assert {"path": ".", "files": 1} in result["directories"]
    assert {"path": "sub", "files": 2} in result["directories"]
