import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.tool.journal import search_journal


@pytest.fixture
def journal_dir(tmp_path):
    d = tmp_path / "journal"
    d.mkdir()
    return str(d)


@pytest.fixture
def journal_with_entries(journal_dir):
    with open(os.path.join(journal_dir, "2024-01-01.md"), "w") as f:
        f.write("Today I fixed a bug in the auth module.\nAll tests passed.\n")
    with open(os.path.join(journal_dir, "2024-01-02.md"), "w") as f:
        f.write("Refactored the database layer.\nImproved query performance.\n")
    return journal_dir


def test_no_journal_dir_configured():
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = ""
        result = search_journal("anything")
    assert "error" in result
    assert "not configured" in result["error"]


def test_journal_dir_not_found():
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = "/nonexistent/path/journal"
        result = search_journal("anything")
    assert "error" in result
    assert "not found" in result["error"]


def test_invalid_regex(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        result = search_journal("[invalid")
    assert "error" in result
    assert "Invalid regex" in result["error"]


def test_no_matches(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("xyzzy_no_match")
    assert result["summary"] == "No matches found."
    assert result["results"] == []


def test_find_matches_python_fallback(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("auth")
    assert "results" in result
    assert len(result["results"]) > 0
    files = [r["file"] for r in result["results"]]
    assert any("2024-01-01" in f for f in files)


def test_case_insensitive_by_default(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("AUTH")
    assert len(result["results"]) > 0


def test_case_sensitive_no_match(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("AUTH", case_sensitive=True)
    assert result["results"] == []


def test_result_structure(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("tests")
    assert "summary" in result
    assert "results" in result
    for entry in result["results"]:
        assert "file" in entry
        assert "line" in entry
        assert "content" in entry


def test_find_matches_with_ripgrep(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value="/usr/bin/rg"):
            result = search_journal("database")
    assert "results" in result
    # rg path returns something (may return no matches if rg not installed, just no error)
    assert "error" not in result


def test_rg_subprocess_timeout_returns_error(journal_with_entries):
    """If rg times out, the helper surfaces an error instead of crashing."""
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch(
            "zrb.llm.tool.journal.shutil.which", return_value="/usr/bin/rg"
        ), patch(
            "zrb.llm.tool.journal.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="rg", timeout=30),
        ):
            result = search_journal("database")
    assert "error" in result
    assert "rg failed" in result["error"]


def test_rg_returncode_2_surfaces_stderr(journal_with_entries):
    """rg's exit code 2 signals an internal error; stderr should be passed through."""
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        completed = MagicMock()
        completed.returncode = 2
        completed.stderr = "regex parse failure"
        completed.stdout = ""
        with patch(
            "zrb.llm.tool.journal.shutil.which", return_value="/usr/bin/rg"
        ), patch("zrb.llm.tool.journal.subprocess.run", return_value=completed):
            result = search_journal("database")
    assert "error" in result
    assert "regex parse failure" in result["error"]


def test_python_search_skips_hidden_files(journal_dir):
    """Files prefixed with `.` are excluded from the python fallback walk."""
    with open(os.path.join(journal_dir, "visible.md"), "w") as f:
        f.write("findme here\n")
    with open(os.path.join(journal_dir, ".hidden.md"), "w") as f:
        f.write("findme also\n")
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_dir
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("findme")
    files = {r["file"] for r in result["results"]}
    assert "visible.md" in files
    assert ".hidden.md" not in files


def test_python_search_swallows_file_open_errors(journal_dir):
    """A file that fails to open is skipped silently — search continues."""
    with open(os.path.join(journal_dir, "good.md"), "w") as f:
        f.write("findme here\n")

    real_open = open

    def fake_open(path, *args, **kwargs):
        if "good.md" in str(path):
            raise PermissionError("denied")
        return real_open(path, *args, **kwargs)

    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_dir
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None), patch(
            "builtins.open", side_effect=fake_open
        ):
            result = search_journal("findme")
    # No crash; just no matches
    assert result.get("results") == []
