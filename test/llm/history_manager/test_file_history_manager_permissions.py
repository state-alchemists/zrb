"""Conversation transcripts are as private as the journal and the archive.

`FileHistoryManager` writes the same kind of sensitive data they do (a full
conversation, word for word) and used to create its directory and files with
whatever mode `os.makedirs`/`open` gave them under the process umask.
"""

import os
import stat

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.util.owner_only import DIR_MODE, FILE_MODE

needs_posix_modes = pytest.mark.skipif(
    os.name != "posix", reason="POSIX mode bits (the mode under test)"
)


def _save(manager: FileHistoryManager, name: str) -> None:
    manager.update(name, [ModelRequest(parts=[UserPromptPart(content="hi")])])
    manager.save(name, write_backup=False)


@needs_posix_modes
def test_a_new_history_dir_and_file_are_created_owner_only(tmp_path):
    history_dir = str(tmp_path / "history")
    old_umask = os.umask(0o022)
    try:
        manager = FileHistoryManager(history_dir)
        _save(manager, "hello")
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE(os.stat(history_dir).st_mode) == DIR_MODE
    assert (
        stat.S_IMODE(os.stat(os.path.join(history_dir, "hello.json")).st_mode)
        == FILE_MODE
    )


@needs_posix_modes
def test_a_backup_file_is_created_owner_only(tmp_path, monkeypatch):
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_HISTORY_BACKUP_RETAIN", 5, raising=False)
    history_dir = str(tmp_path / "history")
    old_umask = os.umask(0o022)
    try:
        manager = FileHistoryManager(history_dir)
        manager.update("hello", [ModelRequest(parts=[UserPromptPart(content="hi")])])
        manager.save("hello", write_backup=True)
    finally:
        os.umask(old_umask)

    backups = [n for n in os.listdir(history_dir) if n != "hello.json"]
    assert backups, "expected a backup file to have been written"
    assert (
        stat.S_IMODE(os.stat(os.path.join(history_dir, backups[0])).st_mode)
        == FILE_MODE
    )


@needs_posix_modes
def test_an_existing_history_dir_does_not_narrow_unrelated_content(tmp_path):
    """LLM_HISTORY_DIR is configured by the user, not created exclusively by
    zrb -- the permission migration for a pre-existing directory must narrow
    only zrb's own entries, never the root's own mode or any other content
    the configured directory already held."""
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    os.chmod(history_dir, 0o755)
    unrelated_dir = history_dir / "unrelated-project"
    unrelated_dir.mkdir()
    unrelated_file = unrelated_dir / "config.yaml"
    unrelated_file.write_text("shared: true\n", encoding="utf-8")
    os.chmod(unrelated_dir, 0o755)
    os.chmod(unrelated_file, 0o644)

    manager = FileHistoryManager(str(history_dir))
    _save(manager, "hello")

    assert stat.S_IMODE(os.stat(history_dir).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(unrelated_dir).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(unrelated_file).st_mode) == 0o644
    assert (
        stat.S_IMODE(os.stat(os.path.join(history_dir, "hello.json")).st_mode)
        == FILE_MODE
    )
