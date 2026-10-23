"""Verbatim archives are collected with the conversation that pointed at them.

An archive is the only copy of the text a summary dropped, so it is deleted only
when nothing refers to it any more — never merely because it is old, and never
while the summary that names it is still on disk.
"""

import os
import time

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.llm.summarizer.verbatim_archive import archive_lock_path, verbatim_archive_path

OLD = 40 * 24 * 60 * 60


@pytest.fixture
def history_dir(tmp_path):
    return tmp_path


@pytest.fixture
def retention():
    from unittest.mock import patch

    with patch("zrb.llm.history_manager.file_history_manager.CFG") as cfg:
        cfg.LLM_HISTORY_RETENTION = "30d"
        cfg.LLM_HISTORY_BACKUP_RETAIN = 0
        yield cfg


def _archive(history_dir, name: str, age_seconds: float = OLD) -> str:
    """An archive section written *age_seconds* ago, with its lock sidecar."""
    path = verbatim_archive_path(name, str(history_dir))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("## Compacted earlier — 1 message(s)\n")
    open(archive_lock_path(path), "w").close()
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def _history(history_dir, name: str, body: str = "[]") -> str:
    path = os.path.join(str(history_dir), f"{name}.json")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(body)
    return path


def _pointer_to(history_dir, name: str) -> str:
    """The archive pointer a summary carries, as the history file stores it."""
    path = verbatim_archive_path(name, str(history_dir))
    return f'["## Verbatim history archive", "Read `\\\\`{path}\\\\``"]'


def _save(manager: FileHistoryManager, name: str) -> None:
    manager.update(name, [ModelRequest(parts=[UserPromptPart(content="hi")])])
    manager.save(name, write_backup=False)


def test_an_archive_no_history_refers_to_is_pruned(history_dir, retention):
    """The conversation it belonged to is gone, so nothing can read it back."""
    path = _archive(history_dir, "orphan")
    _history(history_dir, "mine")

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert not os.path.exists(path)


def test_its_lock_sidecar_goes_with_it(history_dir, retention):
    path = _archive(history_dir, "orphan")

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert not os.path.exists(archive_lock_path(path))


def test_an_archive_a_summary_still_points_at_is_kept(history_dir, retention):
    """The pointer is the archive's only purpose: while it is on disk, the text
    behind it must stay readable."""
    path = _archive(history_dir, "kept")
    _history(history_dir, "mine", _pointer_to(history_dir, "kept"))

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(path)


def test_a_recent_archive_is_kept_before_its_history_is_saved(history_dir, retention):
    """Compaction writes the archive, then the history; between the two nothing
    refers to it yet, and deleting it there would lose the only copy."""
    path = _archive(history_dir, "just-written", age_seconds=0)

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(path)


def test_the_session_being_saved_keeps_its_archive(history_dir, retention):
    """Same window, from the other side: the save that triggers the prune may
    land before the file it saves mentions the archive."""
    path = _archive(history_dir, "in-flight")

    _save(FileHistoryManager(str(history_dir)), "in-flight")

    assert os.path.exists(path)


def test_retention_off_keeps_every_archive(history_dir, retention):
    """`LLM_HISTORY_RETENTION=0` means keep every history, so nothing that
    history might point at may be deleted either."""
    retention.LLM_HISTORY_RETENTION = "0"
    path = _archive(history_dir, "orphan")

    _save(FileHistoryManager(str(history_dir)), "fresh-session")

    assert os.path.exists(path)
