"""The one-time narrowing runs when it should, and only then.

The marker is what stops a second walk, so it is also the thing an attacker
would try to plant: a marker that is not zrb's own must not stand in for a
migration, and must not be written through.
"""

import os
import stat

import pytest

from zrb.util.owner_only import FILE_MODE, DIR_MODE, marker_path, tighten_once

needs_posix_modes = pytest.mark.skipif(
    os.name != "posix", reason="POSIX mode bits (the mode under test)"
)


def _legacy_tree(tmp_path):
    """A directory from before the private-mode rule: 0755, readable files."""
    root = tmp_path / "notes"
    root.mkdir()
    os.chmod(root, 0o755)
    note = root / "note.md"
    note.write_text("- Goes by Go.\n", encoding="utf-8")
    os.chmod(note, 0o644)
    return root, note


@needs_posix_modes
def test_a_plain_tree_is_narrowed_and_marked(tmp_path):
    root, note = _legacy_tree(tmp_path)

    tighten_once(str(root))

    assert stat.S_IMODE(os.stat(root).st_mode) == DIR_MODE
    assert stat.S_IMODE(os.stat(note).st_mode) == FILE_MODE
    assert stat.S_ISREG(os.lstat(marker_path(str(root))).st_mode)


@needs_posix_modes
def test_a_marker_symlink_does_not_skip_the_narrowing(tmp_path):
    """A symlink planted at the marker path used to read as "already done",
    leaving a transcript world-readable forever."""
    root, note = _legacy_tree(tmp_path)
    victim = tmp_path / "victim"
    victim.write_text("untouched", encoding="utf-8")
    os.symlink(str(victim), marker_path(str(root)))

    tighten_once(str(root))

    assert stat.S_IMODE(os.stat(root).st_mode) == DIR_MODE
    assert stat.S_IMODE(os.stat(note).st_mode) == FILE_MODE
    assert victim.read_text(encoding="utf-8") == "untouched"
    # The link was replaced by a real marker, so the work is recorded rather
    # than repeated on every run.
    assert not os.path.islink(marker_path(str(root)))
    assert stat.S_ISREG(os.lstat(marker_path(str(root))).st_mode)


@needs_posix_modes
def test_a_dangling_marker_symlink_is_not_written_through(tmp_path):
    """`O_TRUNC` followed a dangling link and created the target outside the
    directory zrb owns; `O_EXCL` refuses instead."""
    root, _ = _legacy_tree(tmp_path)
    target = tmp_path / "outside"
    os.symlink(str(target), marker_path(str(root)))

    tighten_once(str(root))

    assert not os.path.exists(target)
    assert stat.S_IMODE(os.stat(root).st_mode) == DIR_MODE
    assert stat.S_ISREG(os.lstat(marker_path(str(root))).st_mode)


@needs_posix_modes
def test_a_second_call_leaves_a_reopened_file_alone(tmp_path):
    """The marker is a promise not to keep changing modes behind the user."""
    root, note = _legacy_tree(tmp_path)
    tighten_once(str(root))
    os.chmod(note, 0o644)

    tighten_once(str(root))

    assert stat.S_IMODE(os.stat(note).st_mode) == 0o644
