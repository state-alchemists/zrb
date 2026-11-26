"""Python-level filesystem checks for in-process file tools.

Targets are realpath'd (catching symlink escapes); the check/``open()``
TOCTOU race is accepted, since the agent process itself cannot be jailed
without losing its network loop.

Containment is decided by the disk, not by the spelling. ``os.path.normcase`` is
the identity on POSIX, so a string comparison alone let casing defeat the deny
list: on macOS's default case-insensitive volume ``realpath`` keeps the caller's
casing, and ``~/.SSH/KNOWN_HOSTS`` compared as outside ``~/.ssh`` while being the
same file. A pair is now first compared case-folded, and a fold that reaches the
root is then confirmed by inode — ``(st_dev, st_ino)`` of the root against the
target and each of its existing ancestors — so a case variant lands on the entry
it names on any volume, and nothing is written to find out.

Inode identity only answers for what the disk holds: a deny-read root absent from
the machine is dropped before the comparison, and a configured writable root may
legitimately not exist yet. Where nothing can be confirmed, the two directions
part ways, because being wrong costs different things:

* ``is_read_within`` errs toward refusing. A target whose fold reaches the root
  and that does not exist yet may fold onto it, so it counts as inside. A target
  that *is* on disk and is a different entry stays outside, because on a
  case-sensitive volume ``~/.SSH/x`` really is another directory and refusing it
  would refuse a legitimate read.
* ``is_write_within`` never overrules the disk. Folded spellings that reach the
  root are worth nothing once an inode says the target is a different entry, so
  a case variant on a case-sensitive volume cannot be written through. Only when
  the root is not on disk do the spellings decide.
"""

from __future__ import annotations

import os

from zrb.llm.capabilities.sandbox.policy import (
    SandboxPolicy,
    resolve_real,
    resolved_deny_read_roots,
    resolved_writable_roots,
)

# One filesystem entry, named the way the disk names it: device and inode.
_Identity = tuple[int, int]


def is_read_within(child: str, root: str) -> bool:
    """Whether ``child`` is ``root`` or beneath it, judged as a read would be.

    Over-inclusive on purpose: a target under a folded root that does not exist
    yet is inside, so a case variant can never read its way past the deny list.
    """
    if not _is_same_or_inside_by_spelling(child, root):
        return False
    inside = _inode_within(child, root)
    if inside is None or inside:
        return True
    # Refuted by inode, but only an ancestor could be compared: the unborn tail
    # may still fold onto the root, so a read errs toward refusing.
    return _identity(child) is None


def is_write_within(child: str, root: str) -> bool:
    """Whether ``child`` is ``root`` or beneath it, judged as a write would be.

    The inode decides as soon as ``root`` is on disk, so a case variant that is a
    separate entry on a case-sensitive volume is never granted a write.
    """
    if not _is_same_or_inside_by_spelling(child, root):
        return False
    inside = _inode_within(child, root)
    if inside is None:
        # The root is not on this disk yet: its spellings are all there is.
        return True
    return inside


def check_read(path: str, policy: SandboxPolicy) -> str | None:
    """Return an error message if reading ``path`` is blocked, else ``None``."""
    real = resolve_real(path)
    for root in resolved_deny_read_roots(policy):
        if is_read_within(real, root):
            return (
                f"'{path}' resolves into the protected directory '{root}' "
                "which holds credentials and may not be read"
            )
    return None


def is_read_allowed(path: str, policy: SandboxPolicy) -> bool:
    """Whether reading ``path`` is permitted, for a reader that opens many files.

    The gate judges the argument a call was given; a recursive reader then opens
    every file underneath it, which can be a parent of a deny-read root or a
    workspace directory holding a symlink into one. Callers ask this per file
    instead of per call. A disabled policy allows everything, so the no-sandbox
    path stays exactly as it was.
    """
    if not policy.enabled:
        return True
    return check_read(path, policy) is None


def contains_denied_read_root(path: str, policy: SandboxPolicy) -> str | None:
    """The deny-read root ``path`` contains, or ``None``.

    A recursive reader opens every file beneath the path it is given, and
    ``Grep``'s ripgrep subprocess matches file contents before the per-file
    filter can drop a result. A path that contains a deny-read root therefore
    has to be refused up front, not filtered afterwards. Returns the root so the
    gate can name it; a disabled policy contains nothing, matching
    ``is_read_allowed``.
    """
    if not policy.enabled:
        return None
    real = resolve_real(path)
    for root in resolved_deny_read_roots(policy):
        if is_read_within(root, real):
            return root
    return None


def check_write(path: str, policy: SandboxPolicy) -> str | None:
    """Return an error message if writing ``path`` is blocked, else ``None``.

    A path inside a deny-read root is also unwritable (a secret you cannot
    read you also cannot overwrite or plant — e.g. ``~/.ssh/authorized_keys``).
    """
    real = resolve_real(path)
    for root in resolved_deny_read_roots(policy):
        if is_write_within(real, root):
            return (
                f"'{path}' resolves into the protected directory '{root}' "
                "and may not be written"
            )
    roots = resolved_writable_roots(policy)
    if not any(is_write_within(real, root) for root in roots):
        readable_roots = ", ".join(f"'{r}'" for r in roots)
        return f"'{path}' is outside the sandbox writable roots ({readable_roots})"
    return None


def _is_same_or_inside_by_spelling(child: str, root: str) -> bool:
    """Segment-wise containment after folding case, for the disk to confirm."""
    child_folded = os.path.normcase(child).casefold()
    root_folded = os.path.normcase(root).casefold()
    try:
        return os.path.commonpath([child_folded, root_folded]) == root_folded
    except ValueError:
        # Different drives (Windows) or mixed abs/rel — not within.
        return False


def _inode_within(child: str, root: str) -> bool | None:
    """Whether ``root`` is ``child`` or one of its ancestors, by device and inode.

    ``None`` when ``root`` is not on this disk: there is no inode to look for.
    One directory spelled two ways returns one inode on a case-insensitive
    volume, and on a volume that keeps the spellings apart the wrong one does not
    resolve at all — which is what answers casing without a probe file.
    """
    root_identity = _identity(root)
    if root_identity is None:
        return None
    current = child
    while True:
        if _identity(current) == root_identity:
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def _identity(path: str) -> _Identity | None:
    """The ``(st_dev, st_ino)`` pair naming ``path``, or ``None`` if it is absent."""
    try:
        status = os.stat(path)
    except OSError:
        return None
    return (status.st_dev, status.st_ino)
