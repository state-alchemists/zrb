"""Owner-only (`0700`/`0600`) directories and files for private data.

The archive and the journal are created owner-only. `tighten_once` narrows an
existing directory whose mode is wider, once per directory, leaving a marker
beside it so it is never walked twice.
"""

from __future__ import annotations

import logging
import os
import stat
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

DIR_MODE = 0o700
FILE_MODE = 0o600

# Written beside the directory, not inside it: a marker inside the journal would
# show up in the journal's own git history, and one inside the archive directory
# would sit among the archives it is not.
MARKER_SUFFIX = ".owner-only"


def marker_path(directory: str) -> str:
    """Where *directory*'s "already narrowed" marker lives."""
    return os.path.abspath(directory).rstrip(os.sep) + MARKER_SUFFIX


def tighten_once(
    directory: str,
    owned_entries: "Collection[str] | Callable[[str], bool] | None" = None,
) -> None:
    """Make *directory* and everything under it owner-only, once.

    Only for a directory zrb owns. A symlink is skipped rather than followed, so
    narrowing cannot be redirected onto someone else's file, and an entry that
    refuses the change is left as it is: the prune and the journal write that
    call this must not fail over permissions. Does nothing on Windows, which has
    no mode bits to narrow.

    *owned_entries* narrows only the direct children of *directory* it accepts
    (each one's own mode and everything beneath it), leaving *directory* itself
    and everything it rejects untouched. Give a collection for a fixed set of
    names (the journal's categories), or a predicate over a name for an
    open-ended one (every `.json` history file). Without it the whole tree,
    *directory* included, is narrowed: only safe for a leaf zrb created
    exclusively (the archive's `verbatim` directory), since a directory the user
    configures (the journal or history root) may hold content that other
    readers still need.

    A marker file beside *directory* records that the work is done. It is read
    with `lstat` and created with `O_EXCL`, and counts only when it is a regular
    file owned by the caller with exactly `FILE_MODE`, so a file or symlink that
    another local user plants at that path cannot fake a migration that never
    ran. Anything else at the path is unlinked and replaced once narrowing
    finishes.

    *directory* itself is checked first: `os.walk(followlinks=False)` still
    visits a symlinked top directory, so a symlink planted at the journal or
    archive path would otherwise have its target's tree narrowed instead.
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
        if owned_entries is None:
            _narrow_tree(directory)
        else:
            owns_entry = (
                owned_entries
                if callable(owned_entries)
                else frozenset(owned_entries).__contains__
            )
            _narrow_owned_entries(directory, owns_entry)
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
    """Raise `PermissionError` if *path*, or its nearest *existing* ancestor,
    is a symlink or not a directory.

    The journal and the archive create a leaf beneath a configured root that
    usually exists already, and the OS follows a symlink silently: a link
    planted at the configured path (or at an intermediate directory) would send
    everything written beneath the leaf wherever it points.

    Climbs only until something exists. A missing level has nothing to be a
    symlink, and the first existing level is where a planted link would have to
    sit. It does not climb past that: validating *its* parents would reach
    infrastructure no local attacker controls through zrb's configuration, and
    would refuse a path under a system temp directory because macOS `/var` is
    itself a symlink to `/private/var`.
    """
    current = os.path.abspath(path)
    while True:
        try:
            info = os.lstat(current)
        except OSError:
            parent = os.path.dirname(current)
            if parent == current:
                return
            current = parent
            continue
        if stat.S_ISLNK(info.st_mode):
            raise PermissionError(f"{current!r} is a symlink, not a directory.")
        if not stat.S_ISDIR(info.st_mode):
            raise PermissionError(f"{current!r} exists and is not a directory.")
        return


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


def _narrow_owned_entries(directory: str, owns_entry: "Callable[[str], bool]") -> None:
    """Narrow the direct children of *directory* that `owns_entry` accepts by
    name, leaving *directory* itself and everything it rejects untouched.

    An accepted directory has its whole subtree narrowed (`_narrow_tree`): zrb
    exclusively owns that namespace. An accepted file is narrowed on its own.
    """
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return
    for entry in entries:
        if not owns_entry(entry.name):
            continue
        try:
            info = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        if stat.S_ISDIR(info.st_mode):
            _narrow_tree(entry.path)
        elif stat.S_ISREG(info.st_mode):
            _chmod(entry.path, FILE_MODE)


def makedirs_owner_only(path: str) -> None:
    """Create *path*, and any missing ancestor, owner-only.

    `os.makedirs(mode=...)` applies the mode only to the leaf; intermediate
    directories get `0o777` masked by the umask. Existing levels are checked
    with `reject_symlinked_ancestors`, because `os.path.isdir` follows a
    symlink and a link planted at *path* or an ancestor would read as "already
    there".

    Shared by every subsystem that creates a directory beneath a root the user
    configures (the journal, the conversation history manager). Raises
    `PermissionError` (an `OSError`) when an existing level is a symlink or not
    a directory; a caller wanting another exception type catches and re-raises
    it.

    The check runs again after creating the leaf: a `FileExistsError` from
    `os.mkdir` means something occupied *path* since the first check, and
    treating that as success would trust whatever was planted there.
    """
    reject_symlinked_ancestors(path)
    if os.path.isdir(path):
        return
    parent = os.path.dirname(path)
    if parent and parent != path:
        makedirs_owner_only(parent)
    try:
        os.mkdir(path, DIR_MODE)
    except FileExistsError:
        pass
    reject_symlinked_ancestors(path)


def write_text_owner_only(path: str, content: str) -> None:
    """Write *content* to *path* as UTF-8 text, creating it, and any missing
    directory above it, owner-only.

    `O_NOFOLLOW` refuses a symlink planted at *path* (dangling or not) instead
    of truncating and writing through it. The descriptor is wrapped in a
    buffered file object because a single `os.write()` may write fewer bytes
    than given without raising. Shared by every subsystem that persists private
    text to a user-configured directory.
    """
    makedirs_owner_only(os.path.dirname(path))
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_TRUNC
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0),
        FILE_MODE,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as f:
        f.write(content)


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

    Created with `O_EXCL`, which refuses a path that already exists (a symlink
    included, without resolving it), so nothing standing at the marker is
    truncated or written through. `tighten_once` calls this only after
    `_has_marker` rejected whatever is at the path, so anything found here is
    untrusted: `unlink` removes just that directory entry, never a symlink's
    target, before the marker is created in its place.
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
