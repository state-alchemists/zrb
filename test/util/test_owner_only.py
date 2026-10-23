"""The one-time narrowing runs when it should, and only then.

The marker is what stops a second walk, so it is also the thing an attacker
would try to plant: a marker that is not zrb's own must not stand in for a
migration, and must not be written through.
"""

import os
import stat
from unittest.mock import patch

import pytest

import zrb.util.owner_only as owner_only
from zrb.util.owner_only import (
    DIR_MODE,
    FILE_MODE,
    makedirs_owner_only,
    marker_path,
    reject_symlinked_ancestors,
    tighten_once,
)

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
def test_a_marker_with_the_wrong_mode_does_not_skip_the_narrowing(tmp_path):
    """A regular file at the marker path proves nothing by itself — the mode
    must match too, or a stray file reads as a finished migration."""
    root, note = _legacy_tree(tmp_path)
    marker = marker_path(str(root))
    with open(marker, "wb"):
        pass
    os.chmod(marker, 0o644)

    tighten_once(str(root))

    assert stat.S_IMODE(os.stat(root).st_mode) == DIR_MODE
    assert stat.S_IMODE(os.stat(note).st_mode) == FILE_MODE
    assert stat.S_IMODE(os.lstat(marker).st_mode) == FILE_MODE


@needs_posix_modes
def test_a_marker_owned_by_someone_else_does_not_skip_the_narrowing(
    tmp_path, monkeypatch
):
    """The threat this guards against: another local user, sharing a writable
    parent directory, plants a marker before zrb ever runs. Only ownership
    tells that file apart from one `_write_marker` actually created."""
    root, note = _legacy_tree(tmp_path)
    marker = marker_path(str(root))
    with open(marker, "wb"):
        pass
    os.chmod(marker, FILE_MODE)
    real_euid = os.geteuid()
    monkeypatch.setattr(owner_only.os, "geteuid", lambda: real_euid + 1)

    tighten_once(str(root))

    assert stat.S_IMODE(os.stat(root).st_mode) == DIR_MODE
    assert stat.S_IMODE(os.stat(note).st_mode) == FILE_MODE


@needs_posix_modes
def test_a_symlinked_root_is_not_narrowed_or_followed(tmp_path):
    """`os.walk(directory, followlinks=False)` still visits a symlinked *top*
    directory — `followlinks` only governs recursion into a symlink found
    during the walk — so a symlink planted at the configured path used to have
    its target's tree silently narrowed instead of being refused."""
    outside, outside_file = _legacy_tree(tmp_path)
    link = tmp_path / "configured-root"
    os.symlink(str(outside), str(link))

    tighten_once(str(link))

    assert stat.S_IMODE(os.stat(outside).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(outside_file).st_mode) == 0o644
    assert not os.path.exists(marker_path(str(link)))


@needs_posix_modes
def test_a_symlink_above_an_existing_leaf_does_not_block_it(tmp_path):
    """The climb that refuses a symlinked configured root must not keep
    climbing into infrastructure above it once it reaches something that
    already exists: on macOS `/var` is itself a symlink to `/private/var`,
    and a configured path that resolves through it (as a temp-directory-based
    one typically does) must not be refused for a reason that has nothing to
    do with the path zrb was actually given."""
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "benign-ancestor-link"
    os.symlink(str(outside), str(link))
    root = link / "notes"
    root.mkdir()

    reject_symlinked_ancestors(str(root))  # must not raise


@needs_posix_modes
def test_a_symlinked_ancestor_above_a_missing_leaf_is_still_refused(tmp_path):
    """Climbing stops at the first *existing* level, not the first level
    checked — a symlink there must still be caught even though the leaf
    itself, and its immediate parent, do not exist yet."""
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "malicious-ancestor-link"
    os.symlink(str(outside), str(link))

    with pytest.raises(PermissionError, match="symlink"):
        reject_symlinked_ancestors(str(link / "journal" / "notes"))


@needs_posix_modes
def test_owned_entries_leaves_the_root_and_unlisted_content_alone(tmp_path):
    """A journal root is a directory the user configures directly, and may
    already hold content that belongs to something else — narrowing must
    touch only the names it is told are zrb's own, never the root's own mode
    or anything beside them."""
    root = tmp_path / "notes"
    root.mkdir()
    os.chmod(root, 0o755)
    owned_dir = root / "technical"
    owned_dir.mkdir()
    owned_note = owned_dir / "note.md"
    owned_note.write_text("owned", encoding="utf-8")
    os.chmod(owned_dir, 0o755)
    os.chmod(owned_note, 0o644)
    owned_file = root / "index.md"
    owned_file.write_text("owned index", encoding="utf-8")
    os.chmod(owned_file, 0o644)
    unrelated_dir = root / "unrelated-project"
    unrelated_dir.mkdir()
    unrelated_file = unrelated_dir / "config.yaml"
    unrelated_file.write_text("shared: true\n", encoding="utf-8")
    os.chmod(unrelated_dir, 0o755)
    os.chmod(unrelated_file, 0o644)

    tighten_once(str(root), owned_entries=("technical", "index.md"))

    assert stat.S_IMODE(os.stat(root).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(owned_dir).st_mode) == DIR_MODE
    assert stat.S_IMODE(os.stat(owned_note).st_mode) == FILE_MODE
    assert stat.S_IMODE(os.stat(owned_file).st_mode) == FILE_MODE
    assert stat.S_IMODE(os.stat(unrelated_dir).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(unrelated_file).st_mode) == 0o644


@needs_posix_modes
def test_a_symlink_planted_between_the_check_and_mkdir_is_caught(tmp_path):
    """`FileExistsError` from `os.mkdir` means something now occupies the path
    that did not a moment ago — treating that as success without looking at
    it would trust whatever got planted there in that window."""
    outside = tmp_path / "outside"
    outside.mkdir()
    target = tmp_path / "notes"
    real_mkdir = os.mkdir

    def racy_mkdir(path, mode):
        if path == str(target):
            # A symlink lands exactly where the real directory was about to.
            os.symlink(str(outside), path)
            raise FileExistsError(f"[simulated race] {path}")
        return real_mkdir(path, mode)

    with patch("os.mkdir", side_effect=racy_mkdir):
        with pytest.raises(PermissionError, match="symlink"):
            makedirs_owner_only(str(target))


@needs_posix_modes
def test_a_second_call_leaves_a_reopened_file_alone(tmp_path):
    """The marker is a promise not to keep changing modes behind the user."""
    root, note = _legacy_tree(tmp_path)
    tighten_once(str(root))
    os.chmod(note, 0o644)

    tighten_once(str(root))

    assert stat.S_IMODE(os.stat(note).st_mode) == 0o644
