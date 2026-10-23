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
    """
    if os.name != "posix":
        return
    if os.path.exists(marker_path(directory)):
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
    """Record that *directory* has been narrowed, so this never runs again."""
    descriptor = os.open(
        marker_path(directory), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE
    )
    os.close(descriptor)
