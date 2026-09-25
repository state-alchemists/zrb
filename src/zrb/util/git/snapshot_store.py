"""Snapshots of a working directory as git trees, kept in a private bare
repository whose work tree is the directory.

Nothing is copied, and nothing is written into the directory or into any git
repository under it. `/rewind` (`llm/snapshot/manager.py`) commits these trees
into a persistent store; the self-review gate diffs two of them from a
per-turn temporary store.

A snapshot holds exactly what `snapshot_listing.py` lists — every repository
under the directory by its own ignore rules, nested ones included, and the
loose files outside them up to a budget — fed to `git update-index`. An entry
the listing no longer returns, deleted or ignored since, is dropped from the
index first.

Each snapshot, restore and graft works on an index file of its own, named for
that one operation. A lock a killed git command leaves behind is on that file,
so deleting it can never take another process's lock. The store's named index
is only a stat cache — an operation starts from a copy of it, so a file
unchanged since the last snapshot is not hashed again, and replaces it when
done — and any state of it is a valid start, since every operation first
brings its copy to the current listing. A snapshot also:

- stores bytes exactly: the store's `info/attributes`, which outranks the
  project's `.gitattributes`, disables line-ending and encoding conversion and
  clean/smudge filters, so a restore cannot rewrite a file or write git-lfs
  pointer files into the directory;
- leaves out a file git cannot read rather than failing, and reports how many
  it left out;
- never holds the store itself, wherever it lies.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Iterator, NamedTuple

from zrb.util.git.snapshot_command import (
    SnapshotError,
    get_clean_env,
    get_git_output,
    run_git_command,
)
from zrb.util.git.snapshot_listing import (
    DEFAULT_IGNORE_DIRS,
    Listing,
    get_out_of_scope_paths,
    list_snapshot_paths,
)

_BYTE_EXACT_ATTRIBUTES = "* -text -filter -ident -working-tree-encoding\n"

_IDENTITY_ENV = {
    "GIT_AUTHOR_NAME": "zrb-snapshot",
    "GIT_AUTHOR_EMAIL": "zrb-snapshot@local",
    "GIT_COMMITTER_NAME": "zrb-snapshot",
    "GIT_COMMITTER_EMAIL": "zrb-snapshot@local",
}

# How `git update-index` ends its output when it gives up on a file it could
# not read; the path follows unquoted, then a newline.
_UNREADABLE_PREFIX = "fatal: Unable to process path "

logger = logging.getLogger(__name__)


class Snapshot(NamedTuple):
    #: The snapshot's tree SHA.
    tree: str
    #: Files left out because git could not read them.
    skipped: int = 0
    #: The repositories it holds, relative to the work tree; `""` is the work
    #: tree itself.
    repositories: tuple[str, ...] = ()


class SnapshotStore:
    """A private bare repository whose work tree is *workdir*.

    *index_name* names this user's index inside the store, so several can
    share one store without sharing a lock. *exclude_paths* are further
    absolute paths never to snapshot. With *borrow_objects*, the store reads
    the objects of every repository it lists as alternates instead of storing
    its own copy of every tracked file — only for a short-lived store, since a
    repository's garbage collection may prune what an old snapshot needs."""

    def __init__(
        self,
        git_dir: str,
        workdir: str,
        index_name: str = "index",
        ignore_dirs: Iterable[str] = DEFAULT_IGNORE_DIRS,
        exclude_paths: Iterable[str] = (),
        borrow_objects: bool = False,
    ):
        # Absolute: git runs with the work tree as its cwd.
        self._git_dir = os.path.realpath(git_dir)
        self._workdir = os.path.realpath(workdir)
        self._index_name = index_name
        self._ignore_dirs = frozenset(ignore_dirs)
        self._exclude_paths = [self._git_dir] + [
            os.path.realpath(p) for p in exclude_paths
        ]
        self._borrow_objects = borrow_objects
        self._initialized = False

    @classmethod
    def create_temporary(cls, workdir: str) -> "SnapshotStore":
        """A new store in an owner-only temporary directory, borrowing the
        listed repositories' objects. `delete` it when done."""
        return cls.open_temporary(tempfile.mkdtemp(prefix="zrb-snapshot-"), workdir)

    @classmethod
    def open_temporary(cls, git_dir: str, workdir: str) -> "SnapshotStore":
        """The store `create_temporary` made at *git_dir*, reopened."""
        return cls(git_dir, workdir, borrow_objects=True)

    @property
    def git_dir(self) -> str:
        return self._git_dir

    @property
    def index(self) -> str:
        return os.path.join(self._git_dir, self._index_name)

    @property
    def work_tree(self) -> str:
        """The snapshotted directory; snapshot paths are relative to it."""
        return self._workdir

    def delete(self) -> None:
        """Remove the store and every object its snapshots wrote.

        Git writes object files read-only, which Windows refuses to delete, so
        each one refused is made writable and removed again — a store left
        behind would keep copies of untracked files, secrets included.

        Safe to call more than once, and on a store that was never created:
        cleanup paths race, and a second delete must not mask the error that
        triggered the first. A store removed between the check below and
        `rmtree` reaches the error handler as `FileNotFoundError`, which it
        treats as done.

        Never raises, for the same reason: every caller is a cleanup path. A
        store it could not fully remove is logged as a warning naming its
        path instead, so its copies of untracked files can be removed by
        hand."""
        if not os.path.isdir(self._git_dir):
            return
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(self._git_dir, onexc=_remove_read_only)
            else:
                shutil.rmtree(
                    self._git_dir,
                    onerror=lambda fn, path, info: _remove_read_only(fn, path, info[1]),
                )
        except OSError:
            pass  # whatever is left is reported below
        if os.path.exists(self._git_dir):
            logger.warning(
                "Could not delete snapshot store %s; it may hold copies of "
                "untracked files. Remove it by hand.",
                self._git_dir,
            )

    def ensure(self, deadline: float | None = None) -> None:
        """Create the store if needed and (re)write its attribute rules.
        Raises SnapshotError when git cannot set it up."""
        if self._initialized:
            return
        if not os.path.isdir(os.path.join(self._git_dir, "objects")):
            os.makedirs(self._git_dir, mode=0o700, exist_ok=True)
            get_git_output(["init", "-q", "--bare", self._git_dir], None, deadline)
        # Owner-only, whatever the umask: the store holds copies of untracked
        # files. A closed top directory keeps other users out of everything
        # under it. Applied on every open, so a store created with looser
        # permissions is tightened too.
        os.chmod(self._git_dir, 0o700)
        info = os.path.join(self._git_dir, "info")
        os.makedirs(info, exist_ok=True)
        _write(os.path.join(info, "attributes"), _BYTE_EXACT_ATTRIBUTES)
        self._initialized = True

    def snapshot(self, deadline: float | None = None) -> Snapshot:
        """Snapshot the directory and write its tree. Raises
        `SnapshotBudgetError` when the directory holds too many files outside
        every repository."""
        with self._operation_index(from_cache=True) as index:
            listing, skipped = self._index_directory(index, deadline)
            tree = self.git(["write-tree"], index=index, deadline=deadline).strip()
        return Snapshot(tree, skipped, tuple(listing.repositories))

    def restore(self, treeish: str, deadline: float | None = None) -> None:
        """Make the directory match *treeish*: rewrite changed files, recreate
        deleted ones, and remove files created since. A path the listing
        leaves out now — ignored or excluded since *treeish* was taken — is
        neither overwritten nor recreated."""
        with self._operation_index(from_cache=True) as index:
            listing, _ = self._index_directory(index, deadline)
            target = self._create_tree_in_scope(treeish, listing, deadline)
            self.git(
                ["read-tree", "-u", "--reset", target], index=index, deadline=deadline
            )

    def diff(
        self, before: str, after: str, deadline: float | None = None
    ) -> tuple[list[str], str]:
        """The paths (relative to `work_tree`) that differ between two trees,
        and their unified diff.

        The paths are exact — NUL-separated, so git neither quotes an unusual
        name nor loses one to trimming — and without rename detection, so a
        renamed file's old path is listed too. The diff ignores the user's
        external diff tool and colour settings, and replaces undecodable bytes
        with U+FFFD: it goes to a model, which may reject lone surrogates."""
        names = self.git(
            ["diff", "--name-only", "-z", "--no-renames", before, after],
            deadline=deadline,
        )
        diff = self.git(
            ["diff", "--no-ext-diff", "--no-color", before, after],
            deadline=deadline,
            errors="replace",
        )
        return [name for name in names.split("\0") if name], diff.strip()

    def create_grafted_tree(
        self, tree: str, prefix: str, commit: str, deadline: float | None = None
    ) -> str:
        """*tree* with *commit*'s tree added under *prefix*, which *tree* must
        not hold yet."""
        with self._operation_index(from_cache=False) as index:
            self.git(["read-tree", tree], index=index, deadline=deadline)
            self.git(
                ["read-tree", f"--prefix={prefix}/", commit],
                index=index,
                deadline=deadline,
            )
            return self.git(["write-tree"], index=index, deadline=deadline).strip()

    def git(
        self,
        args: list[str],
        index: str | None = None,
        stdin: str | None = None,
        deadline: float | None = None,
        errors: str = "surrogateescape",
    ) -> str:
        """Run a git command against the store; its stdout. Raises
        SnapshotError when it fails."""
        result = self.run_git(args, index, stdin, deadline, errors)
        if result.returncode != 0:
            raise SnapshotError(f"git {args[0]} failed: {result.stderr.strip()}")
        return result.stdout

    def run_git(
        self,
        args: list[str],
        index: str | None = None,
        stdin: str | None = None,
        deadline: float | None = None,
        errors: str = "surrogateescape",
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command against the store, whatever its exit code."""
        self.ensure(deadline)
        env = {
            **get_clean_env(),
            **_IDENTITY_ENV,
            "GIT_INDEX_FILE": index or self.index,
        }
        argv = [
            "git",
            # A global `core.fsmonitor` would start a watcher daemon per store.
            "-c",
            "core.fsmonitor=false",
            f"--git-dir={self._git_dir}",
            f"--work-tree={self._workdir}",
            *args,
        ]
        return run_git_command(
            argv, self._workdir, deadline, env, stdin, errors, f"git {args[0]}"
        )

    @contextmanager
    def _operation_index(self, from_cache: bool) -> Iterator[str]:
        """An index file for one operation. With *from_cache* it starts as a
        copy of the store's named index and replaces it when the operation
        succeeds; without, it starts empty and is discarded. It is deleted,
        with any lock a killed command left on it, however the operation
        ends."""
        index = f"{self.index}.{uuid.uuid4().hex}"
        if from_cache and os.path.exists(self.index):
            shutil.copyfile(self.index, index)
        try:
            yield index
            if from_cache:
                try:
                    os.replace(index, self.index)
                except OSError as e:  # e.g. held open on Windows: a stale cache
                    logger.debug(f"Could not update the snapshot index cache: {e}")
        finally:
            for leftover in (index, f"{index}.lock"):
                _remove_if_present(leftover)

    def _index_directory(
        self, index: str, deadline: float | None
    ) -> tuple[Listing, int]:
        """Bring *index* to the directory's current listing; return the
        listing and how many files git could not read."""
        self.ensure(deadline)
        listing = list_snapshot_paths(
            self._workdir,
            self._ignore_dirs,
            self._exclude_paths,
            deadline,
        )
        if self._borrow_objects:
            self._borrow_from(listing.repositories, deadline)
        listed = set(listing.paths)
        indexed = self.git(["ls-files", "-z"], index=index, deadline=deadline)
        unlisted = [path for path in indexed.split("\0") if path and path not in listed]
        if unlisted:
            result = self._update_index(["--force-remove"], unlisted, index, deadline)
            if result.returncode != 0:
                raise SnapshotError(f"git update-index failed: {result.stderr.strip()}")
        return listing, self._add_readable(listing.paths, index, deadline)

    def _add_readable(
        self, paths: list[str], index: str, deadline: float | None
    ) -> int:
        """Add *paths* to the index — `--remove` drops one deleted from disk —
        and return how many were left out because git could not read them.

        `update-index` gives up at the first unreadable file and names it, so
        that file is left out and the rest are fed again; each rerun re-stats
        the others instead of hashing them. The file is found by matching each
        path against the end of git's output, not by parsing a path out of
        it: git prints the name raw, so a newline in it would split a parsed
        line."""
        remaining, skipped = list(paths), 0
        while remaining:
            result = self._update_index(
                ["--add", "--remove"], remaining, index, deadline
            )
            if result.returncode == 0:
                break
            unreadable = next(
                (
                    path
                    for path in remaining
                    if result.stderr.endswith(f"{_UNREADABLE_PREFIX}{path}\n")
                ),
                None,
            )
            if unreadable is None:
                raise SnapshotError(f"git update-index failed: {result.stderr.strip()}")
            remaining.remove(unreadable)
            skipped += 1
        return skipped

    def _update_index(
        self, flags: list[str], paths: list[str], index: str, deadline: float | None
    ) -> subprocess.CompletedProcess[str]:
        return self.run_git(
            ["update-index", *flags, "-z", "--stdin"],
            index=index,
            stdin="".join(f"{path}\0" for path in paths),
            deadline=deadline,
        )

    def _borrow_from(self, repositories: list[str], deadline: float | None) -> None:
        """Add each listed repository's object database to the store's
        alternates, keeping the ones already there: an earlier snapshot's
        objects must stay readable."""
        alternates = os.path.join(self._git_dir, "objects", "info", "alternates")
        try:
            with open(alternates, encoding="utf-8") as f:
                known = [line for line in f.read().splitlines() if line]
        except OSError:
            known = []
        for base in repositories:
            where = (
                os.path.join(self._workdir, *base.split("/")) if base else self._workdir
            )
            objects = get_git_output(
                ["rev-parse", "--git-path", "objects"], where, deadline
            ).strip()
            path = os.path.normpath(os.path.join(where, objects))
            if path not in known:
                known.append(path)
        os.makedirs(os.path.dirname(alternates), exist_ok=True)
        _write(alternates, "".join(f"{path}\n" for path in known))

    def _create_tree_in_scope(
        self, treeish: str, listing: Listing, deadline: float | None
    ) -> str:
        """*treeish*'s tree minus the paths the listing would leave out now."""
        with self._operation_index(from_cache=False) as index:
            self.git(["read-tree", treeish], index=index, deadline=deadline)
            paths = self.git(["ls-files", "-z"], index=index, deadline=deadline)
            out = get_out_of_scope_paths(
                self._workdir,
                [path for path in paths.split("\0") if path],
                listing.repositories,
                self._ignore_dirs,
                self._exclude_paths,
                deadline,
            )
            if out:
                self.git(
                    ["update-index", "--force-remove", "-z", "--stdin"],
                    index=index,
                    stdin="".join(f"{path}\0" for path in out),
                    deadline=deadline,
                )
            return self.git(["write-tree"], index=index, deadline=deadline).strip()


def _remove_read_only(fn: Callable[[str], Any], path: str, exc: Any) -> None:
    """`rmtree` error handler: a path already gone — another cleanup won the
    race — is done; a refused removal is retried once the path is writable;
    what still fails is left in place for `delete` to report."""
    if isinstance(exc, FileNotFoundError):
        return
    try:
        os.chmod(path, stat.S_IWRITE)
        fn(path)
    except OSError:
        pass


def _remove_if_present(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


def _write(path: str, content: str) -> None:
    # LF on Windows too: git reads an `alternates` line ending in `\r` as a
    # path that does not exist.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
