"""Narrow a private directory that was written before zrb made one.

The archive and the journal are now created ``0700``/``0600``, but a directory
from an earlier version keeps whatever mode it was made with, and its files may
be readable by others. `tighten_once` fixes that in place, once per directory,
and leaves a marker beside it so it is never walked twice.
"""

from __future__ import annotations

import logging
import os
import stat

DIR_MODE = 0o700
FILE_MODE = 0o600

# Written beside the directory, not inside it: a marker inside the journal would
# show up in the journal's own git history, and one inside the archive directory
# would sit among the archives it is not.
MARKER_SUFFIX = ".owner-only"


def marker_path(directory: str) -> str:
    """Where *directory*'s "already narrowed" marker lives."""
    return os.path.abspath(directory).rstrip(os.sep) + MARKER_SUFFIX


def tighten_once(directory: str) -> None:
    """Make *directory* and everything under it owner-only, once.

    Only for a directory zrb owns: a symlink is skipped rather than followed, so
    narrowing cannot be redirected onto somebody else's file, and an entry that
    refuses the change is left as it is instead of failing the caller — the
    prune and the journal write that call this must not fail over permissions.
    Windows has no mode bits to narrow, so there it does nothing.

    The marker decides whether the work is already done, so it is read with
    `lstat` and created exclusively: one planted at its path cannot stand in for
    a migration that never ran, and cannot redirect the write that records one.
    A regular file only counts as that marker when it is owned by the caller and
    carries exactly `FILE_MODE` — another local user sharing the parent
    directory can create a file at that path, but cannot make it theirs, so it
    cannot fake a migration that never happened. Anything else at the path
    (a symlink, or a regular file that fails that check) is unlinked and
    replaced once narrowing finishes.

    *directory* itself is checked first: `os.walk(directory, followlinks=False)`
    still visits a symlinked top directory — `followlinks` only governs whether
    it recurses into a symlink found *during* the walk — so a symlink planted at
    the configured journal or archive path would otherwise have its target's
    tree silently narrowed instead.
    """
    if os.name != "posix":
        return
    if _is_symlink(directory):
        logging.getLogger(__name__).warning(
            f"Not restricting permissions under {directory}: it is a symlink, "
            "and narrowing would have followed it onto whatever it points at."
        )
        return
    if _has_marker(directory):
        return
    try:
        _narrow_tree(directory)
        _write_marker(directory)
    except OSError as e:
        # A partial pass leaves no marker, so the next call tries again. The
        # module logger reaches the same handlers as `CFG.LOGGER` (the root one)
        # without `util` having to import `config`.
        logging.getLogger(__name__).warning(
            f"Could not restrict permissions under {directory}: {e}"
        )


def _is_symlink(path: str) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode)
    except OSError:
        return False


def reject_symlinked_ancestors(path: str) -> None:
    """Raise `PermissionError` if *path*, or any existing ancestor of it, is a
    symlink or not a directory.

    Both the journal and the archive create a leaf beneath a configured root
    that usually already exists (`os.makedirs`, or a hand-rolled walk that
    stops at the first existing level) — and neither one ever used to look at
    that root's own type. A symlink planted at the configured path (or any
    directory above the leaf) was therefore followed silently by the OS, and
    everything written beneath the leaf landed wherever that link pointed,
    even though the leaf itself was never a symlink. This walks from *path* up
    to the filesystem root, `lstat`-ing every level that currently exists; a
    level that does not exist yet is skipped, since there is nothing there yet
    to be a symlink — the caller is the one that creates it.
    """
    current = os.path.abspath(path)
    while True:
        try:
            info = os.lstat(current)
        except OSError:
            pass
        else:
            if stat.S_ISLNK(info.st_mode):
                raise PermissionError(f"{current!r} is a symlink, not a directory.")
            if not stat.S_ISDIR(info.st_mode):
                raise PermissionError(f"{current!r} exists and is not a directory.")
        parent = os.path.dirname(current)
        if parent == current:
            return
        current = parent


def _has_marker(directory: str) -> bool:
    """Whether a marker this function can trust is already in place.

    `lstat`, not `stat`: a symlink at the marker path must not read as a finished
    migration, or the narrowing it stands for would be skipped. A regular file
    only counts when it is ours (owner and mode match what `_write_marker`
    creates) — anyone else's parent-writable plant fails one of those checks and
    is treated as no marker at all.
    """
    try:
        info = os.lstat(marker_path(directory))
    except OSError:
        return False
    if not stat.S_ISREG(info.st_mode):
        return False
    return info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == FILE_MODE


def _narrow_tree(directory: str) -> None:
    """Walk *directory* without following symlinks, narrowing as it goes."""
    for root, subdirs, files in os.walk(directory, followlinks=False):
        for name in files:
            _chmod(os.path.join(root, name), FILE_MODE)
        for name in subdirs:
            _chmod(os.path.join(root, name), DIR_MODE)
    _chmod(directory, DIR_MODE)


def _chmod(path: str, mode: int) -> None:
    """Set *mode* on *path* if it is something other than a symlink or a socket."""
    try:
        info = os.lstat(path)
    except OSError:
        return
    if stat.S_ISLNK(info.st_mode) or not (
        stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)
    ):
        return
    if stat.S_IMODE(info.st_mode) == mode:
        return
    try:
        os.chmod(path, mode)
    except OSError:
        # Not ours to change, or a filesystem without modes; leave it alone.
        pass


def _write_marker(directory: str) -> None:
    """Record that *directory* has been narrowed, so this never runs again.

    Created exclusively (`O_EXCL`), which refuses a path that already exists — a
    symlink included, without having to resolve it — so nothing standing at the
    marker can be truncated or written through. `O_NOFOLLOW` is added where the
    platform has it, for the reader's benefit as much as the kernel's.

    `tighten_once` only calls this after `_has_marker` already rejected whatever
    is at the path, so anything found here — a symlink, or a regular file owned
    by someone else, or one with the wrong mode — is untrusted. `unlink` removes
    only that directory entry, never a symlink's target, before the marker is
    created in its place.
    """
    target = marker_path(directory)
    try:
        _create_marker(target)
    except FileExistsError:
        os.unlink(target)
        _create_marker(target)


def _create_marker(target: str) -> None:
    """Create *target* empty, failing if anything is already at that path."""
    descriptor = os.open(
        target,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0),
        FILE_MODE,
    )
    os.close(descriptor)
