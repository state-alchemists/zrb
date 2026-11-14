"""What a restore may touch, decided apart from the repository that writes it.

`SnapshotStore` holds the private bare repository — indexes, trees, git. A
restore asks a second question of the same directory: given a snapshot and the
directory as it is now, which paths may be rewritten, which came into being
after the snapshot and must be kept, and which stands in the way. That decision
lives here, so a change to the policy is a change to this file and never to the
plumbing that carries it out.
"""

from __future__ import annotations

import os
import stat
import unicodedata
from collections.abc import Iterable
from typing import TYPE_CHECKING, NamedTuple

from zrb.llm.snapshot.listing import (
    DEFAULT_IGNORE_DIRS,
    Listing,
    get_out_of_scope_paths,
)

if TYPE_CHECKING:
    # Annotation-only: `Snapshot` is the store's vocabulary, and importing it
    # at runtime would close a cycle between the two modules.
    from zrb.llm.snapshot.store import Snapshot

# `FILE_ATTRIBUTE_REPARSE_POINT`: set on a Windows junction or symlink.
_REPARSE_POINT = 0x400


class RestoreTarget(NamedTuple):
    """One restore's snapshot tree, and the directory it is applied to now.

    Paths are relative to *workdir* and `/`-separated, as the listing and the
    tree write them.
    """

    workdir: str
    #: The snapshot's tree, as paths.
    paths: list[str]
    #: What the directory holds now.
    listing: Listing
    #: The files git could not read now.
    unreadable: list[str]
    #: The paths git holds for the directory now: `{path: (mode, sha)}`.
    current: dict[str, tuple[str, str]]
    ignore_dirs: Iterable[str] = DEFAULT_IGNORE_DIRS
    exclude_paths: Iterable[str] = ()
    deadline: float | None = None


class RestorePlan(NamedTuple):
    """The paths a restore must leave alone, and the ones in its way.

    *in_the_way* is reported rather than rewritten: something no snapshot holds
    stands where the tree would write, so that path is kept and the restore
    says it could not make it match.
    """

    left_alone: frozenset[str]
    in_the_way: frozenset[str]


def plan_restore(target: RestoreTarget) -> RestorePlan:
    """Which of *target*'s snapshot paths may be written, and which are in the
    way.

    A path is left alone when a listing of the directory would leave it out
    now, when git cannot read it now, when the snapshot left it out, or when
    the snapshot shows something unlisted in its place.
    """
    out_of_scope = get_out_of_scope_paths(
        target.workdir,
        target.paths,
        target.listing.repositories,
        target.ignore_dirs,
        target.exclude_paths,
        target.deadline,
    )
    # A path the tree holds now but the listing did not see is under a
    # directory that could not be read: writing over it is irreversible.
    unseen = [
        path
        for path in target.paths
        if path not in target.current
        and is_under_unreadable_directory(target.workdir, path)
    ]
    # `left_out` adds the files too large to snapshot: the ignored ones are in
    # `out_of_scope` already.
    left_alone = (
        out_of_scope | set(target.unreadable) | set(unseen) | set(target.listing.left_out)
    )
    in_the_way = find_in_the_way(
        target.workdir,
        [path for path in target.paths if path not in left_alone],
        target.current,
    )
    return RestorePlan(frozenset(left_alone), frozenset(in_the_way))


def find_in_the_way(
    workdir: str, paths: list[str], current: dict[str, tuple[str, str]]
) -> set[str]:
    """The *paths* git could write only by destroying something no snapshot
    holds. `read-tree -u --reset` removes an untracked file or directory in the
    way of what it writes, and anything the operation index lacks is untracked
    to it: a directory holding an ignored file where the snapshot has a file or
    symlink, an ignored file or a FIFO where it has a file or needs a directory.
    A listed path in the way is the restore's own to replace, and so is a
    directory holding only listed files; a real directory above a path is not in
    its way."""
    listed = {_fold(path) for path in current}
    verdicts: dict[str, bool] = {}  # an ancestor: whether it blocks

    def is_in_the_way(rel: str, is_ancestor: bool) -> bool:
        if _fold(rel) in listed:
            return False
        try:
            info = os.lstat(_absolute(workdir, rel))
        except (FileNotFoundError, NotADirectoryError):
            return False  # nothing there, or under a listed file
        except OSError:
            return True  # cannot tell: left alone
        if _is_real_directory(info):
            return not is_ancestor and _has_unlisted(workdir, rel, listed)
        return True

    in_the_way = set()
    for path in paths:
        parts = path.split("/")
        for depth in range(1, len(parts)):
            ancestor = "/".join(parts[:depth])
            if ancestor not in verdicts:
                verdicts[ancestor] = is_in_the_way(ancestor, is_ancestor=True)
            if verdicts[ancestor]:
                in_the_way.add(path)
                break
        else:
            if is_in_the_way(path, is_ancestor=False):
                in_the_way.add(path)
    return in_the_way


def find_lacking(
    workdir: str, current: dict[str, tuple[str, str]], wanted: set[str]
) -> list[str]:
    """The current paths the target lacks. On a filesystem that ignores letter
    case or Unicode normalization (macOS, Windows), a current path the target
    holds in another case or form is the same file: the target's version is
    written to it, and it is not lacking, so it is never removed as created
    since — which would delete that file."""
    missing = {_fold(path): path for path in wanted if path not in current}
    twins = {
        path
        for path in current
        if (twin := missing.get(_fold(path))) is not None
        and twin != path
        and os.path.lexists(_absolute(workdir, twin))
    }
    return sorted(path for path in current if path not in wanted | twins)


def find_created_since(
    lacking: list[str], snapshot: "Snapshot", repositories: list[str]
) -> list[str]:
    """The *lacking* files *snapshot* shows did not exist when it was taken: it
    would have listed them, since it neither left them out nor failed to read
    them. The files of a repository listed now (*repositories*) that it did not
    list are kept instead: a worktree or clone made since, whose own history
    holds its work.

    Left-out paths are matched with `_fold`; repositories exactly. Both err
    toward keeping."""
    then = {_fold(repository) for repository in snapshot.repositories}
    files = {
        _fold(path)
        for path in (*snapshot.unreadable, *snapshot.left_out)
        if not path.endswith("/")
    }
    directories = [_fold(path[:-1]) for path in snapshot.left_out if path.endswith("/")]

    def is_recorded(path: str) -> bool:
        key = _fold(path)
        if key in files:
            return True
        # A left-out directory covers what its own repository would list there,
        # not a repository inside it, which listed itself.
        owner = _find_repository(key, then)
        return any(
            key.startswith(f"{directory}/")
            and _find_repository(directory, then) == owner
            for directory in directories
        )

    def is_in_new_repository(path: str) -> bool:
        repository = _find_repository(path, repositories)
        return bool(repository) and repository not in snapshot.repositories

    return [
        path
        for path in lacking
        if not is_recorded(path) and not is_in_new_repository(path)
    ]


def find_clashes(wanted: list[str], kept: list[str]) -> set[str]:
    """The *wanted* paths a *kept* file stands in the way of: one under a kept
    file, or a file where a kept one needs a directory."""
    kept_files = {_fold(path) for path in kept}
    kept_directories = {parent for path in kept for parent in _parents(_fold(path))}
    return {
        path
        for path in wanted
        if _fold(path) in kept_directories
        or any(parent in kept_files for parent in _parents(_fold(path)))
    }


def is_under_unreadable_directory(workdir: str, path: str) -> bool:
    """Whether an existing directory on *path*'s way down from *workdir* cannot
    be read — the listing could not see what it holds."""
    parts = path.split("/")[:-1]
    for depth in range(1, len(parts) + 1):
        directory = os.path.join(workdir, *parts[:depth])
        if not os.path.isdir(directory):
            return False
        if not os.access(directory, os.R_OK | os.X_OK):
            return True
    return False


def _has_unlisted(workdir: str, rel: str, listed: set[str]) -> bool:
    """Whether the directory at *rel* holds anything the listing does not — or
    anything it cannot look into, which counts the same."""
    pending = [rel]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(_absolute(workdir, directory)) as it:
                entries = list(it)
        except OSError:
            return True
        for entry in entries:
            child = f"{directory}/{entry.name}"
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                return True
            if _is_real_directory(info):
                pending.append(child)
            elif _fold(child) not in listed:
                return True
    return False


def _absolute(workdir: str, rel: str) -> str:
    return os.path.join(workdir, *rel.split("/"))


def _find_repository(path: str, repositories: Iterable[str]) -> str | None:
    """The deepest of *repositories* holding *path*, or None when none does."""
    holding = [r for r in repositories if not r or path.startswith(f"{r}/")]
    return max(holding, key=len, default=None)


def _fold(path: str) -> str:
    """*path* as a filesystem that ignores letter case and Unicode
    normalization (macOS, Windows) sees it: `é` composed or not, any case."""
    return unicodedata.normalize("NFC", path).casefold()


def _is_real_directory(info: os.stat_result) -> bool:
    """A directory, not a symlink or a Windows junction to one."""
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISDIR(info.st_mode) and not attributes & _REPARSE_POINT


def _parents(path: str) -> list[str]:
    """`a/b/c` → `a`, `a/b`."""
    parts = path.split("/")
    return ["/".join(parts[:depth]) for depth in range(1, len(parts))]
