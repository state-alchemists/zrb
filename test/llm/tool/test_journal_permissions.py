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
        mock_cfg.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 25
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
            "technical", "a-slug", "A title", "context", "finding", "source",
            applies_when="while zrb 3.29 is released",

            hud_line="finding",)
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


@needs_posix_modes
def test_a_symlinked_journal_root_is_refused(tmp_path):
    """`os.path.isdir()` follows a symlink; a symlinked configured root used to
    read as "the directory is already there" and every write that followed
    landed in whatever it pointed at instead."""
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "notes"
    os.symlink(str(outside), str(link))
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(link)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"

        with pytest.raises(ValueError, match="symlink"):
            ensure_journal_tree()

    assert list(outside.iterdir()) == []


@needs_posix_modes
def test_a_symlinked_note_path_is_refused_not_overwritten(writable_journal, tmp_path):
    """`O_TRUNC | O_CREAT` without `O_NOFOLLOW` followed a symlink planted at a
    note's path and overwrote whatever it pointed at."""
    ensure_journal_tree()
    secret = tmp_path / "secret.md"
    secret.write_text("do not touch\n", encoding="utf-8")
    note_path = os.path.join(writable_journal, "technical", "a-slug.md")
    os.symlink(str(secret), note_path)

    with pytest.raises(OSError):
        write_journal_note(
            "technical", "a-slug", "A title", "context", "finding", "source",
            applies_when="while zrb 3.29 is released",

            hud_line="finding",)

    assert secret.read_text(encoding="utf-8") == "do not touch\n"


@needs_posix_modes
def test_an_existing_journal_dir_does_not_narrow_unrelated_content(writable_journal):
    """LLM_JOURNAL_DIR is configured by the user, not created exclusively by
    zrb -- the permission migration for a pre-existing directory must narrow
    only the journal's own entries, never the root's own mode or any other
    content the configured directory already held."""
    root = writable_journal
    unrelated_dir = os.path.join(root, "unrelated-project")
    os.makedirs(unrelated_dir)
    unrelated_file = os.path.join(unrelated_dir, "config.yaml")
    with open(unrelated_file, "w", encoding="utf-8") as f:
        f.write("shared: true\n")
    os.chmod(unrelated_file, 0o644)
    os.chmod(unrelated_dir, 0o755)
    os.chmod(root, 0o755)

    log_activity("first thing")

    assert stat.S_IMODE(os.stat(root).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(unrelated_dir).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(unrelated_file).st_mode) == 0o644
    assert stat.S_IMODE(os.stat(os.path.join(root, "technical")).st_mode) == DIR_MODE
    assert stat.S_IMODE(os.stat(os.path.join(root, "index.md")).st_mode) == FILE_MODE
