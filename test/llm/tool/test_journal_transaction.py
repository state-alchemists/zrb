"""The public batch seam: one lock, one commit, and a rollback on failure.

Every tool takes the journal lock itself, so an import of forty notes used to
reach past the tools into the private helpers under a hand-held `_open_journal`.
`journal_transaction` is the seam that replaces that: it holds the lock once,
hands out the lock-free halves of the tools, and commits once at the end.
"""

import os
import subprocess
from unittest.mock import patch

import pytest

from zrb.llm.tool.journal_write import journal_transaction, write_journal_note


@pytest.fixture
def git_journal(tmp_path):
    """Patch CFG for the writer module with git-backing explicitly on."""
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = True
        mock_cfg.LLM_GIT_CMD_TIMEOUT = 5000
        yield str(root)


def _git(root: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", root, *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def _head(root: str) -> str:
    return _git(root, "rev-parse", "HEAD").strip()


def _subjects(root: str) -> list[str]:
    return _git(root, "log", "--format=%s").strip().splitlines()


def _note_exists(root: str, slug: str) -> bool:
    return os.path.isfile(os.path.join(root, "technical", f"{slug}.md"))


def _index_mentions(root: str, slug: str, relative: str = "index.md") -> bool:
    with open(os.path.join(root, relative), "r", encoding="utf-8") as f:
        return slug in f.read()


def _write_baseline_note() -> None:
    """One ordinary write, so the repo exists with exactly one commit on top of
    its init commit and the tree is clean."""
    write_journal_note("technical", "existing", "Existing", "ctx", "found", "s:1")


def test_a_transaction_writing_two_notes_produces_one_commit(git_journal):
    with journal_transaction() as transaction:
        first = transaction.write_note(
            "technical", "first", "First", "ctx", "found it", "s:1"
        )
        second = transaction.write_note(
            "technical", "second", "Second", "ctx", "found it", "s:2"
        )

    # The strings are the tools' own, so a batch can be logged like any write.
    assert first == "Wrote technical/first.md"
    assert second == "Wrote technical/second.md"
    assert _subjects(git_journal) == ["batch: 2 change(s)", "init: journal tree"]
    assert _note_exists(git_journal, "first")
    assert _note_exists(git_journal, "second")


def test_a_transaction_commits_activity_and_deletes_under_one_message(git_journal):
    _write_baseline_note()
    with journal_transaction("import: 44 notes") as transaction:
        transaction.log_activity("imported the archive", files=["notes.md"])
        transaction.delete_note("technical", "existing")

    # Newest first: the batch is one commit, not one per change.
    assert _subjects(git_journal) == [
        "import: 44 notes",
        "write: technical/existing",
        "init: journal tree",
    ]
    assert not _note_exists(git_journal, "existing")


def test_a_zero_change_transaction_commits_nothing(git_journal):
    _write_baseline_note()
    head = _head(git_journal)

    with journal_transaction() as transaction:
        pass

    assert transaction.change_count == 0
    assert _head(git_journal) == head


def test_a_raising_transaction_makes_no_commit_and_restores_the_tree(git_journal):
    """HEAD stays at the entry commit and the tracked files match it: the note
    the body deleted is back, and both indexes list it again."""
    _write_baseline_note()
    head = _head(git_journal)

    with pytest.raises(RuntimeError, match="import failed"):
        with journal_transaction() as transaction:
            transaction.delete_note("technical", "existing")
            raise RuntimeError("import failed")

    assert _head(git_journal) == head
    assert _note_exists(git_journal, "existing")
    assert _index_mentions(git_journal, "existing")
    assert _index_mentions(git_journal, "existing", "technical/index.md")
    assert _git(git_journal, "status", "--porcelain") == ""


def test_a_raising_transaction_commits_no_new_note(git_journal):
    """`reset --hard HEAD` restores tracked content, not the file set: the files
    a failed body created stay on disk untracked, while every index entry that
    pointed at them is gone. Nothing commits, so nothing records them."""
    _write_baseline_note()
    head = _head(git_journal)

    with pytest.raises(RuntimeError, match="import failed"):
        with journal_transaction() as transaction:
            transaction.write_note(
                "technical", "half-written", "Half", "ctx", "found", "s:2"
            )
            transaction.log_activity("about to fail")
            raise RuntimeError("import failed")

    assert _head(git_journal) == head
    assert not _index_mentions(git_journal, "half-written")
    assert not _index_mentions(git_journal, "half-written", "technical/index.md")


def test_a_raising_transaction_leaves_other_edits_untouched(git_journal):
    """Rollback restores only the files the transaction itself touched.

    A note somebody else was editing is not the transaction's to discard — and
    the body's own writes are undone anyway, because the snapshot is per file
    rather than a tree-wide reset.
    """
    _write_baseline_note()
    stray = os.path.join(git_journal, "user", "hand-written.md")
    with open(stray, "w", encoding="utf-8") as f:
        f.write("# Hand written\n")

    with pytest.raises(RuntimeError, match="import failed"):
        with journal_transaction() as transaction:
            transaction.write_note(
                "technical", "half-written", "Half", "ctx", "found", "s:2"
            )
            raise RuntimeError("import failed")

    assert os.path.isfile(stray)
    assert not _note_exists(git_journal, "half-written")
    assert not _index_mentions(git_journal, "half-written")


def test_a_raising_transaction_restores_an_ignored_note(git_journal):
    """Git has no baseline for an ignored file, so a clean status cannot make a
    rollback safe on its own: the snapshot is what brings the old bytes back."""
    _write_baseline_note()
    legacy = os.path.join(git_journal, "technical", "legacy.md")
    with open(legacy, "w", encoding="utf-8") as f:
        f.write("# Legacy finding\n")
    with open(os.path.join(git_journal, ".gitignore"), "a", encoding="utf-8") as f:
        f.write("technical/legacy.md\n")
    _git(
        git_journal,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "-a",
        "-m",
        "an ignored note",
    )
    assert _git(git_journal, "status", "--porcelain").strip() == ""

    with pytest.raises(RuntimeError, match="import failed"):
        with journal_transaction() as transaction:
            transaction.write_note(
                "technical", "legacy", "Legacy", "new ctx", "new finding", "s:9"
            )
            raise RuntimeError("import failed")

    with open(legacy, "r", encoding="utf-8") as f:
        assert f.read() == "# Legacy finding\n"


def test_a_raising_transaction_leaves_the_migration_it_needed(git_journal):
    """Opening a journal is setup, not part of the body.

    The root index an older journal needs is migrated before the snapshot
    starts, so a failed body leaves that migration in place — and still undoes
    every write the body itself made. Setup that survives is idempotent; a
    half-applied body is not.
    """
    _write_baseline_note()
    older = "# Journal\n\n## User\n\n- Goes by Go.\n\n## Active Constraints\n\n"
    with open(os.path.join(git_journal, "index.md"), "w", encoding="utf-8") as f:
        f.write(older)
    _git(
        git_journal,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "-a",
        "-m",
        "an index from an earlier version",
    )
    head = _head(git_journal)

    with pytest.raises(RuntimeError, match="import failed"):
        with journal_transaction() as transaction:
            transaction.write_note(
                "technical", "half-written", "Half", "ctx", "found", "s:2"
            )
            raise RuntimeError("import failed")

    assert _head(git_journal) == head
    with open(os.path.join(git_journal, "index.md"), "r", encoding="utf-8") as f:
        restored = f.read()
    assert "## Agent" in restored, "the migration is setup and stays"
    assert "half-written" not in restored


def test_a_raising_transaction_leaves_a_first_time_journal_whole(git_journal):
    """A journal created by the doomed call is setup too.

    The tree and its initial commit are made before the snapshot starts, so a
    failed body leaves an empty but valid journal — not an initial commit with
    its tracked files deleted underneath it.
    """
    with pytest.raises(RuntimeError, match="import failed"):
        with journal_transaction() as transaction:
            transaction.write_note("technical", "x", "X", "c", "f", "s")
            raise RuntimeError("import failed")

    assert os.path.isfile(os.path.join(git_journal, "index.md"))
    assert os.path.isfile(os.path.join(git_journal, "technical", "index.md"))
    assert _git(git_journal, "status", "--porcelain").strip() == ""
    assert not _note_exists(git_journal, "x")
