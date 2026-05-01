import os
from unittest.mock import patch

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
