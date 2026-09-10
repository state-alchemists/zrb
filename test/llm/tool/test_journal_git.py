"""Journal git-backing: unbounded history and human-recoverable deletes.

The in-file History block (journal_write.py's `_HISTORY_MAX_ENTRIES`) only
keeps the last 3 revisions of a note — see test_journal.py for that behavior.
These tests cover the separate, unbounded safety net: every write/delete
becomes a real git commit, recoverable by a human outside the tools even past
that cap.
"""

import os
import subprocess
from unittest.mock import patch

import pytest

from zrb.llm.tool.journal_write import (
    delete_journal_note,
    ensure_journal_tree,
    write_journal_note,
)


@pytest.fixture
def git_journal(tmp_path):
    """Patch CFG for the writer module with git-backing explicitly on."""
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = True
        mock_cfg.LLM_GIT_CMD_TIMEOUT = 5000
        yield str(root)


def _git(root: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", root, *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def test_ensure_journal_tree_alone_does_not_initialize_git(git_journal):
    """Git init/first-commit only happens under `_journal_lock` (inside a
    writer call), never from `ensure_journal_tree()` alone — otherwise two
    first-time writers could race `git init` outside any lock."""
    root = ensure_journal_tree()
    assert not os.path.isdir(os.path.join(root, ".git"))


def test_write_journal_note_initializes_a_git_repo(git_journal):
    write_journal_note("technical", "some-note", "Title", "ctx", "finding", "source")
    assert os.path.isdir(os.path.join(git_journal, ".git"))


def test_git_disabled_creates_no_git_repo(tmp_path):
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        ensure_journal_tree()
    assert not os.path.isdir(os.path.join(str(root), ".git"))


def test_write_journal_note_produces_a_commit(git_journal):
    write_journal_note("technical", "some-note", "Title", "ctx", "finding A", "source")
    log = _git(git_journal, "log", "--oneline", "--", "technical/some-note.md")
    assert len(log.strip().splitlines()) == 1

    write_journal_note("technical", "some-note", "Title", "ctx", "finding B", "source")
    log = _git(git_journal, "log", "--oneline", "--", "technical/some-note.md")
    assert len(log.strip().splitlines()) == 2


def test_delete_journal_note_is_recoverable_via_git_history(git_journal):
    write_journal_note(
        "technical", "some-note", "Title", "ctx", "the original finding", "source"
    )
    delete_journal_note("technical", "some-note")

    assert not os.path.isfile(os.path.join(git_journal, "technical", "some-note.md"))
    recovered = _git(git_journal, "show", "HEAD~1:technical/some-note.md")
    assert "the original finding" in recovered


def test_hung_git_does_not_break_writes(git_journal):
    """A hanging `git` (GPG-sign prompt, stale index.lock) must time out
    rather than freezing the whole journal call."""
    with patch(
        "zrb.llm.tool.journal_write.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="git", timeout=1),
    ):
        result = write_journal_note(
            "technical", "some-note", "Title", "ctx", "finding", "source"
        )
    assert result == "Wrote technical/some-note.md"
    assert os.path.isfile(os.path.join(git_journal, "technical", "some-note.md"))
    assert not os.path.isdir(os.path.join(git_journal, ".git"))


def test_git_commands_pass_a_timeout(git_journal):
    with patch(
        "zrb.llm.tool.journal_write.subprocess.run", wraps=subprocess.run
    ) as mock_run:
        write_journal_note(
            "technical", "some-note", "Title", "ctx", "finding", "source"
        )
    assert mock_run.call_args_list, "expected at least one git subprocess call"
    for call in mock_run.call_args_list:
        assert "timeout" in call.kwargs


def test_missing_git_binary_does_not_break_writes(git_journal):
    with patch(
        "zrb.llm.tool.journal_write.subprocess.run",
        side_effect=FileNotFoundError("no git"),
    ):
        result = write_journal_note(
            "technical", "some-note", "Title", "ctx", "finding", "source"
        )
    assert result == "Wrote technical/some-note.md"
    assert os.path.isfile(os.path.join(git_journal, "technical", "some-note.md"))
    assert not os.path.isdir(os.path.join(git_journal, ".git"))
