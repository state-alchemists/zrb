"""`ensure_journal_tree` must hand `tighten_once` a complete tree.

Narrowing used to run before the category directories and index files were
created, so a first-time journal kept whatever mode `os.makedirs`/`open` gave
it under the process umask — world-readable under a typical `022`.
"""

import os
import stat
from unittest.mock import patch

import pytest

from zrb.llm.tool.journal_write import (
    ACTIVITY_DIR,
    NOTE_CATEGORIES,
    ensure_journal_tree,
    log_activity,
    write_journal_note,
)
from zrb.util.owner_only import DIR_MODE, FILE_MODE

needs_posix_modes = pytest.mark.skipif(
    os.name != "posix", reason="POSIX mode bits (the mode under test)"
)


@pytest.fixture
def writable_journal(tmp_path):
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        yield str(root)


@needs_posix_modes
def test_a_first_time_tree_is_created_owner_only(writable_journal):
    old_umask = os.umask(0o022)
    try:
        root = ensure_journal_tree()
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE(os.stat(root).st_mode) == DIR_MODE
    for name in (*NOTE_CATEGORIES, ACTIVITY_DIR):
        category_dir = os.path.join(root, name)
        assert stat.S_IMODE(os.stat(category_dir).st_mode) == DIR_MODE
        index = os.path.join(category_dir, "index.md")
        assert stat.S_IMODE(os.stat(index).st_mode) == FILE_MODE
    assert stat.S_IMODE(os.stat(os.path.join(root, "index.md")).st_mode) == FILE_MODE


@needs_posix_modes
def test_files_created_after_the_marker_stay_owner_only(writable_journal):
    """The one-time `tighten_once` marker is written on the first call; every
    day file, month/year index and note created on a *later* call used to be
    created under the process umask instead, since nothing ever revisits
    them."""
    old_umask = os.umask(0o022)
    try:
        ensure_journal_tree()
        log_activity("did a thing")
        write_journal_note(
            "technical", "a-slug", "A title", "context", "finding", "source"
        )
    finally:
        os.umask(old_umask)

    root = writable_journal
    note = os.path.join(root, "technical", "a-slug.md")
    assert stat.S_IMODE(os.stat(note).st_mode) == FILE_MODE
    activity = os.path.join(root, ACTIVITY_DIR)
    for dirpath, dirnames, filenames in os.walk(activity):
        for name in dirnames:
            assert (
                stat.S_IMODE(os.stat(os.path.join(dirpath, name)).st_mode) == DIR_MODE
            )
        for name in filenames:
            assert (
                stat.S_IMODE(os.stat(os.path.join(dirpath, name)).st_mode) == FILE_MODE
            )
