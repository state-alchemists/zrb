"""Which files a working-directory snapshot holds.

Git's own walk of a work tree stops at any directory holding a repository and
records it as a gitlink, so `git add -A` never sees inside a nested
repository. The listing is built here instead, repository by repository:

- A directory inside a git repository is listed by that repository —
  `git ls-files --cached --others --exclude-standard` — so its `.gitignore`
  files, above the directory too, its `info/exclude` and the user's global
  excludes all apply.
- Each nested repository is listed the same way, by itself, recursively:
  one the listing reports — an untracked one as `dir/`, a submodule as a
  gitlink — and one inside a directory the repository ignores, which is
  searched for repositories and nothing else. A repository is often ignored
  by its parent only so the parent stops reporting it — a folder of cloned
  child repositories, or the worktrees `EnterWorktree` creates under
  `.zrb/worktree/` — and its files are no less the user's.
- A directory outside every repository is walked, and a repository found
  there is listed by itself. Outside a repository `DEFAULT_IGNORE_DIRS` is the
  only rule, so those loose files count toward `LOOSE_FILE_LIMIT` and
  `LOOSE_BYTE_LIMIT`; past either, the listing raises `SnapshotBudgetError`.

`DEFAULT_IGNORE_DIRS` and the excluded paths apply everywhere, tracked files
included, and are never searched for repositories.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable

from zrb.util.git.snapshot_command import (
    SnapshotError,
    get_git_output,
    run_git_command,
)

#: Directories that are large, regenerable, and almost never hand-edited,
#: excluded even where no `.gitignore` names them.
DEFAULT_IGNORE_DIRS: frozenset[str] = frozenset(
    {
        # Python
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".eggs",
        # Node / JS
        "node_modules",
        ".next",
        ".nuxt",
        ".turbo",
        ".parcel-cache",
        # Generic caches
        ".cache",
    }
)

#: The most files a listing takes from outside every repository.
LOOSE_FILE_LIMIT = 5000
#: The most bytes a listing takes from outside every repository.
LOOSE_BYTE_LIMIT = 200 * 1024 * 1024

_GITLINK_MODE = "160000"


class SnapshotBudgetError(SnapshotError):
    """The files outside every repository exceed the listing's budget."""


@dataclass
class Listing:
    """What one snapshot holds. Paths are relative to the working directory
    and `/`-separated."""

    #: Every file to snapshot.
    paths: list[str] = field(default_factory=list)
    #: Where each repository was listed from; `""` is the working directory.
    repositories: list[str] = field(default_factory=list)


def list_snapshot_paths(
    workdir: str,
    ignore_dirs: Iterable[str] = DEFAULT_IGNORE_DIRS,
    exclude_paths: Iterable[str] = (),
    deadline: float | None = None,
) -> Listing:
    """The files a snapshot of *workdir* holds (see the module docstring).
    *exclude_paths* are absolute paths never listed."""
    scope = _Scope(workdir, ignore_dirs, exclude_paths)
    return _Lister(scope, deadline).list()


def get_out_of_scope_paths(
    workdir: str,
    paths: list[str],
    repositories: list[str],
    ignore_dirs: Iterable[str] = DEFAULT_IGNORE_DIRS,
    exclude_paths: Iterable[str] = (),
    deadline: float | None = None,
) -> set[str]:
    """Which of *paths* a listing of *workdir* would leave out now: those
    under an ignored or excluded directory, and those the repository owning
    them ignores — the deepest of *repositories* each lies in. As in the
    listing, a file that repository tracks is never ignored, whatever its
    patterns say: a force-added file, or `.env.example` under `.env*`. A path
    that no longer exists is judged the same way, so a restore can still
    recreate it."""
    scope = _Scope(workdir, ignore_dirs, exclude_paths)
    out = {path for path in paths if scope.is_excluded(path)}
    bases = sorted(repositories, key=len, reverse=True)
    owned: dict[str, list[str]] = {}
    for path in paths:
        base = next((b for b in bases if _is_under(path, b)), None)
        if path not in out and base is not None:
            owned.setdefault(base, []).append(path[len(base) + 1 :] if base else path)
    for base, rels in owned.items():
        result = run_git_command(
            # Without `--no-index`: a tracked path is never reported.
            ["git", "check-ignore", "-z", "--stdin"],
            scope.absolute(base),
            deadline,
            stdin="".join(f"{rel}\0" for rel in rels),
        )
        if result.returncode not in (0, 1):  # 1: none of them is ignored
            raise SnapshotError(f"git check-ignore failed: {result.stderr.strip()}")
        out.update(_join(base, rel) for rel in result.stdout.split("\0") if rel)
    return out


def get_fork_point(repository: str, deadline: float | None = None) -> str | None:
    """The commit the repository at *repository* started from — its oldest
    `HEAD` reflog entry, which a worktree's creation or a clone writes — or
    its current `HEAD` when that reflog is gone. None when it started from
    nothing: before its first commit, or when its oldest entry is that first
    commit (`commit (initial)`), since then everything in it is new."""
    log = run_git_command(
        ["git", "reflog", "show", "--format=%H %gs", "HEAD"], repository, deadline
    )
    entries = log.stdout.splitlines() if log.returncode == 0 else []
    if entries:
        sha, _, subject = entries[-1].partition(" ")
        return None if subject.startswith("commit (initial)") else sha
    head = run_git_command(
        ["git", "rev-parse", "--verify", "-q", "HEAD"], repository, deadline
    )
    if head.returncode != 0:
        return None
    return head.stdout.strip() or None


class _Scope:
    """The working directory, and the directories never listed in it."""

    def __init__(
        self, workdir: str, ignore_dirs: Iterable[str], exclude_paths: Iterable[str]
    ):
        self.workdir = os.path.realpath(workdir)
        self.ignore_dirs = frozenset(ignore_dirs)
        self._excluded = [
            rel.replace(os.sep, "/")
            for path in exclude_paths
            if (rel := _relpath_inside(os.path.realpath(path), self.workdir))
        ]

    def absolute(self, rel: str) -> str:
        return os.path.join(self.workdir, *rel.split("/")) if rel else self.workdir

    def is_excluded(self, rel: str, is_dir: bool = False) -> bool:
        """Whether *rel* — a file, or with *is_dir* a directory — lies under an
        ignored directory or an excluded path."""
        parts = rel.split("/")
        directories = parts if is_dir else parts[:-1]
        if any(part in self.ignore_dirs for part in directories):
            return True
        return any(rel == ex or rel.startswith(ex + "/") for ex in self._excluded)


class _Lister:
    def __init__(self, scope: _Scope, deadline: float | None):
        self._scope = scope
        self._deadline = deadline
        self._listing = Listing()
        self._seen: set[str] = set()
        self._loose_files = 0
        self._loose_bytes = 0

    def list(self) -> Listing:
        workdir = self._scope.workdir
        inside = run_git_command(
            ["git", "rev-parse", "--is-inside-work-tree"], workdir, self._deadline
        )
        if inside.returncode == 0 and inside.stdout.strip() == "true":
            self._list_repository("")
        else:
            self._walk("")
        return self._listing

    def _list_repository(self, base: str) -> None:
        """List the repository at *base* by its own rules, then the nested
        repositories it reports and those in the directories it ignores."""
        where = self._scope.absolute(base)
        key = os.path.normcase(os.path.realpath(where))
        if key in self._seen:
            return
        tracked = self._git(["ls-files", "--cached", "--stage", "-z"], where)
        excludes = [f"--exclude={d}/" for d in sorted(self._scope.ignore_dirs)]
        # Git reports an untracked nested repository as `dir/` and does not
        # descend into it; an ordinary untracked directory it lists file by
        # file under this repository's rules. `--directory` would collapse the
        # ordinary ones too, and their files would lose those rules.
        others = self._git(
            ["ls-files", "--others", "--exclude-standard", *excludes, "-z"], where
        )
        # Ignored directories, each reported once and not descended into.
        ignored = self._git(
            [
                "ls-files",
                "--others",
                "--ignored",
                "--exclude-standard",
                "--directory",
                "-z",
            ],
            where,
        )
        self._seen.add(key)
        self._listing.repositories.append(base)
        nested: list[str] = []
        for entry in tracked.split("\0"):
            meta, _, path = entry.partition("\t")
            if meta.split(" ", 1)[0] == _GITLINK_MODE:
                nested.append(path)
            elif path:
                self._add(_join(base, path))
        for path in others.split("\0"):
            if path.endswith("/"):
                nested.append(path[:-1])
            elif path:
                self._add(_join(base, path))
        for path in nested:
            self._list_nested(_join(base, path))
        for path in ignored.split("\0"):
            if path.endswith("/"):
                self._find_repositories(_join(base, path[:-1]))

    def _list_nested(self, rel: str, walk_if_broken: bool = True) -> None:
        """A directory holding a repository of its own: listed by it. When git
        cannot list it — a worktree whose repository is gone, say — it is
        walked with *walk_if_broken*, else left out. An uninitialized
        submodule holds nothing to list."""
        path = self._scope.absolute(rel)
        if self._scope.is_excluded(rel, is_dir=True) or not os.path.lexists(
            os.path.join(path, ".git")
        ):
            return
        try:
            self._list_repository(rel)
        except SnapshotBudgetError:
            raise
        except SnapshotError:
            if walk_if_broken:
                self._walk(rel)

    def _find_repositories(self, top: str) -> None:
        """List each repository inside *top*, a directory its repository
        ignores; nothing else in it is listed."""
        pending = [top]
        while pending:
            rel = pending.pop()
            if self._scope.is_excluded(rel, is_dir=True):
                continue
            path = self._scope.absolute(rel)
            if os.path.lexists(os.path.join(path, ".git")):
                self._list_nested(rel, walk_if_broken=False)
                continue
            try:
                with os.scandir(path) as it:
                    entries = list(it)
            except OSError:
                continue
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(_join(rel, entry.name))
                except OSError:
                    continue

    def _walk(self, top: str) -> None:
        """List a directory outside every repository, file by file."""
        pending = [top]
        while pending:
            rel = pending.pop()
            try:
                with os.scandir(self._scope.absolute(rel)) as it:
                    entries = list(it)
            except OSError:
                continue
            for entry in entries:
                if entry.name == ".git":
                    continue
                child = _join(rel, entry.name)
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                if not is_dir:
                    if not self._scope.is_excluded(child):
                        self._count_loose(entry)
                        self._listing.paths.append(child)
                elif self._scope.is_excluded(child, is_dir=True):
                    continue
                elif os.path.lexists(os.path.join(entry.path, ".git")):
                    self._list_nested(child)
                else:
                    pending.append(child)

    def _count_loose(self, entry: os.DirEntry[str]) -> None:
        self._loose_files += 1
        try:
            self._loose_bytes += entry.stat(follow_symlinks=False).st_size
        except OSError:
            pass
        workdir = self._scope.workdir
        if self._loose_files > LOOSE_FILE_LIMIT:
            raise SnapshotBudgetError(
                f"{workdir} has more than {LOOSE_FILE_LIMIT} files outside any "
                "git repository"
            )
        if self._loose_bytes > LOOSE_BYTE_LIMIT:
            raise SnapshotBudgetError(
                f"{workdir} has more than {LOOSE_BYTE_LIMIT // 2**20} MB of files "
                "outside any git repository"
            )

    def _add(self, path: str) -> None:
        if not self._scope.is_excluded(path):
            self._listing.paths.append(path)

    def _git(self, args: list[str], where: str) -> str:
        return get_git_output(args, where, self._deadline)


def _join(base: str, path: str) -> str:
    return f"{base}/{path}" if base else path


def _is_under(path: str, base: str) -> bool:
    return not base or path.startswith(base + "/")


def _relpath_inside(path: str, root: str) -> str | None:
    """*path* relative to *root* when it lies strictly inside it, else None."""
    try:
        rel = os.path.relpath(path, root)
    except ValueError:  # another drive on Windows: never inside
        return None
    if rel == "." or rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return None
    return rel
