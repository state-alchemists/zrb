"""Glob, the Code tool and LS agree about which files exist.

`LS` started hiding what `.gitignore` excludes; the other two tools kept
reporting the ignored tree, so the same directory had two shapes depending on
which tool asked.
"""

import os
import subprocess
import sys

import pytest

from zrb.llm.tool.code import get_file_metadatas
from zrb.llm.tool.file import glob_files, list_files
from zrb.llm.tool.file_observation import clear_observed
from zrb.llm.tool.git_visible import git_visible_files, without_gitignored


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


def test_glob_hides_gitignored(tmp_path):
    """An ignored generated tree must not appear in a name search."""
    _init_checkout(tmp_path)
    _write(tmp_path / ".gitignore", "generated/\n")
    _write(tmp_path / "generated" / "artifact.py")
    _write(tmp_path / "kept.py")

    files = glob_files("**/*.py", path=str(tmp_path)).get("files", [])

    assert "kept.py" in files
    assert os.path.join("generated", "artifact.py") not in files


def test_glob_gitignore_false_returns_ignored(tmp_path):
    _init_checkout(tmp_path)
    _write(tmp_path / ".gitignore", "generated/\n")
    _write(tmp_path / "generated" / "artifact.py")

    files = glob_files("**/*.py", path=str(tmp_path), gitignore=False).get("files", [])

    assert os.path.join("generated", "artifact.py") in files


def test_glob_and_ls_report_the_same_files(tmp_path):
    """The two tools answer the same question; they must not disagree."""
    _init_checkout(tmp_path)
    _write(tmp_path / ".gitignore", "output/\n")
    _write(tmp_path / "output" / "bundle.js")
    _write(tmp_path / "src" / "app.js")

    globbed = sorted(glob_files("**/*.js", path=str(tmp_path)).get("files", []))
    listed = sorted(
        path
        for path in list_files(str(tmp_path)).get("files", [])
        if path.endswith(".js")
    )

    assert globbed == listed
    assert globbed == [os.path.join("src", "app.js")]


def test_glob_outside_a_checkout_still_matches(tmp_path):
    """No repository above the directory: the git filter must not hide it all."""
    _write(tmp_path / "plain.py")

    files = glob_files("*.py", path=str(tmp_path)).get("files", [])

    assert "plain.py" in files


def test_analyze_code_skips_files_git_ignores(tmp_path):
    """A directory analysis must not read and bill for ignored output."""
    _init_checkout(tmp_path)
    _write(tmp_path / ".gitignore", "generated/\n")
    _write(tmp_path / "generated" / "huge.py", "IGNORED_MARKER = 1\n")
    _write(tmp_path / "kept.py", "KEPT_MARKER = 1\n")

    visible = git_visible_files(str(tmp_path))
    metadatas = get_file_metadatas(str(tmp_path), ["py"], None, [], visible=visible)

    paths = [metadata["path"] for metadata in metadatas]
    assert paths == ["kept.py"]


def test_get_file_metadatas_without_a_visible_set_reads_everything(tmp_path):
    _write(tmp_path / "one.py", "ONE = 1\n")

    metadatas = get_file_metadatas(str(tmp_path), ["py"], None, [])

    assert [metadata["path"] for metadata in metadatas] == ["one.py"]


def test_without_gitignored_passes_through_outside_a_checkout(tmp_path):
    _write(tmp_path / "plain.txt")

    assert without_gitignored(str(tmp_path), ["plain.txt"]) == ["plain.txt"]


def test_git_visible_files_reports_a_non_ascii_name_unquoted(tmp_path):
    """`git ls-files` C-quotes unusual names; the raw path is what is on disk."""
    _init_checkout(tmp_path)
    _write(tmp_path / "café.py")

    visible = git_visible_files(str(tmp_path))

    assert visible is not None
    assert "café.py" in visible


def test_glob_hides_nothing_it_should_keep_in_a_non_ascii_name(tmp_path):
    _init_checkout(tmp_path)
    _write(tmp_path / ".gitignore", "generated/\n")
    _write(tmp_path / "café.py")
    _write(tmp_path / "generated" / "artifact.py")

    files = glob_files("*.py", path=str(tmp_path)).get("files", [])

    assert "café.py" in files
    assert os.path.join("generated", "artifact.py") not in files


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="a Windows filename is UTF-16 and cannot hold a byte that is not valid UTF-8",
)
def test_a_name_that_is_not_valid_utf8_does_not_break_the_filter(tmp_path):
    """A filename is not required to be valid UTF-8; git must not crash the tool."""
    _init_checkout(tmp_path)
    name = os.fsdecode(b"bad-\xff.py")
    (tmp_path / name).write_text("x", encoding="utf-8")

    visible = git_visible_files(str(tmp_path))

    assert visible is not None
    assert os.path.normpath(name) in visible
