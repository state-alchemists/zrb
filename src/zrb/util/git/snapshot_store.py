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
    run_git_binary,
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

_GITLINK_MODE = "160000"

# How `git update-index` ends its output when it gives up on a file it could
# not read; the path follows unquoted, then a newline.
_UNREADABLE_PREFIX = "fatal: Unable to process path "

logger = logging.getLogger(__name__)


class Snapshot(NamedTuple):
    #: The snapshot's tree SHA.
    tree: str
    #: Files left out because git could not read them.
    unreadable: tuple[str, ...] = ()
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
        try:
            holds = os.path.commonpath([self._git_dir, self._workdir]) == self._git_dir
        except ValueError:  # another drive on Windows
            holds = False
        if holds:
            # Deleting the store would delete the work tree with it.
            raise ValueError(
                f"A snapshot store cannot hold its own work tree: {self._git_dir}"
            )
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
            listing, unreadable = self._index_directory(index, deadline)
            tree = self.git(["write-tree"], index=index, deadline=deadline).strip()
        return Snapshot(tree, tuple(unreadable), tuple(listing.repositories))

    def restore(
        self,
        treeish: str,
        keep: Iterable[str] = (),
        deadline: float | None = None,
    ) -> list[str]:
        """Make the directory match *treeish*, and return the paths it could
        not — empty when the directory now matches. *keep* are the files that
        snapshot could not read.

        Each path is decided by its state now (ADR-0101 has the table):

        - listed and readable: rewritten to *treeish*'s version, or, when
          *treeish* lacks it, removed only if it was created since;
        - unreadable, or under a directory that cannot be read: left alone —
          its content is in no snapshot, so writing over it is irreversible;
        - ignored or excluded: left alone;
        - absent: recreated from *treeish*.

        A write the filesystem refuses — a file another program holds open,
        a directory without write permission — does not stop the others: git
        writes every file it can, and the paths left behind are returned, so
        restoring again finishes once the cause is gone."""
        with self._operation_index(from_cache=True) as index:
            listing, unreadable = self._index_directory(index, deadline)
            before = self.git(["write-tree"], index=index, deadline=deadline).strip()
            current = _index_entries(
                self.git(["ls-files", "--stage", "-z"], index=index, deadline=deadline)
            )
            target = self._create_restore_target(
                treeish, listing, unreadable, current, deadline
            )
            wanted = set(self._list_tree(target, deadline))
            lacking = self._find_lacking(current, wanted)
            # Pass 1: write the target, keeping every current file it lacks —
            # such a file may have existed then without being captured.
            kept = self._edit_tree(
                target,
                add=[
                    f"{current[path][0]} {current[path][1]}\t{path}" for path in lacking
                ],
                deadline=deadline,
            )
            self._write_tree_to_disk(kept, index, deadline)
            # Pass 2: with the target's own ignore rules back on disk, remove
            # the files it lacks because they were created since.
            created = self._find_created_since(
                lacking, wanted, listing, set(keep), deadline
            )
            final = self._edit_tree(kept, remove=created, deadline=deadline)
            if created:
                self._write_tree_to_disk(final, index, deadline)
            return self._find_left_behind(before, final, index, deadline)

    def _create_restore_target(
        self,
        treeish: str,
        listing: Listing,
        unreadable: list[str],
        current: dict[str, tuple[str, str]],
        deadline: float | None,
    ) -> str:
        """*treeish*'s tree minus every path a restore must leave alone:
        those out of scope now, the files git cannot read now, and — when
        not listed — the ones under a directory that cannot be read."""
        paths = self._list_tree(treeish, deadline)
        out = get_out_of_scope_paths(
            self._workdir,
            paths,
            listing.repositories,
            self._ignore_dirs,
            self._exclude_paths,
            deadline,
        )
        unseen = [
            path
            for path in paths
            if path not in current and self._is_under_unreadable_directory(path)
        ]
        return self._edit_tree(
            treeish,
            remove=sorted(out | set(unreadable) | set(unseen)),
            deadline=deadline,
        )

    def _find_lacking(
        self, current: dict[str, tuple[str, str]], wanted: set[str]
    ) -> list[str]:
        """The current paths the target lacks. On a filesystem that ignores
        letter case (macOS, Windows), a current path the target holds in
        another case is the same file: the target's version is written to
        it, and it is not lacking, so it is never removed as created since —
        which would delete that file."""
        missing = {path.casefold(): path for path in wanted if path not in current}
        twins = {
            path
            for path in current
            if (twin := missing.get(path.casefold())) is not None
            and twin != path
            and os.path.lexists(os.path.join(self._workdir, *twin.split("/")))
        }
        return sorted(path for path in current if path not in wanted | twins)

    def _find_created_since(
        self,
        lacking: list[str],
        wanted: set[str],
        listing: Listing,
        keep: set[str],
        deadline: float | None,
    ) -> list[str]:
        """The *lacking* files that did not exist when the target was taken.
        Run once the target's ignore rules are back on disk. A file is kept
        when those rules leave it out (it existed then, ignored), when the
        target could not read it (*keep*), or when its repository is one the
        target holds nothing of — a worktree or clone made since, whose own
        history holds its work."""
        left_out = get_out_of_scope_paths(
            self._workdir,
            lacking,
            listing.repositories,
            self._ignore_dirs,
            self._exclude_paths,
            deadline,
        )
        made_since = [
            base
            for base in listing.repositories
            if base and not any(path.startswith(f"{base}/") for path in wanted)
        ]
        return [
            path
            for path in lacking
            if path not in keep
            and path not in left_out
            and not any(path.startswith(f"{base}/") for base in made_since)
        ]

    def _list_tree(self, treeish: str, deadline: float | None) -> list[str]:
        return _tree_paths(
            self.git(["ls-tree", "-r", "-z", "--name-only", treeish], deadline=deadline)
        )

    def _find_left_behind(
        self, before: str, final: str, index: str, deadline: float | None
    ) -> list[str]:
        """The paths a restore meant to change — where *final* differs from
        *before* — that the directory does not hold as *final* has them."""
        meant = set(self.diff(before, final, deadline)[0])
        self._index_directory(index, deadline)
        actual = self.git(["write-tree"], index=index, deadline=deadline).strip()
        return [path for path in self.diff(final, actual, deadline)[0] if path in meant]

    def _is_under_unreadable_directory(self, path: str) -> bool:
        """Whether an existing directory on *path*'s way down from the work
        tree cannot be read — the listing could not see what it holds."""
        parts = path.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            directory = os.path.join(self._workdir, *parts[:depth])
            if not os.path.isdir(directory):
                return False
            if not os.access(directory, os.R_OK | os.X_OK):
                return True
        return False

    def _write_tree_to_disk(
        self, tree: str, index: str, deadline: float | None
    ) -> None:
        """`read-tree -u --reset` *tree* into the directory. A write it cannot
        make is not raised: git makes every other one, and the caller finds
        what is left behind by comparing the directory with *tree*."""
        result = self.run_git(
            ["read-tree", "-u", "--reset", tree], index=index, deadline=deadline
        )
        if result.returncode != 0:
            logger.warning(
                f"Restore could not write every file: {result.stderr.strip()}"
            )

    def diff(
        self,
        before: str,
        after: str,
        deadline: float | None = None,
        exclude: Iterable[str] = (),
    ) -> tuple[list[str], str]:
        """The paths (relative to `work_tree`) that differ between two trees,
        and their unified diff.

        The paths are exact — NUL-separated, so git neither quotes an unusual
        name nor loses one to trimming — and without rename detection, so a
        renamed file's old path is listed too. The diff ignores the user's
        external diff tool and colour settings, and replaces undecodable bytes
        with U+FFFD: it goes to a model, which may reject lone surrogates.
        *exclude* are paths left out of both."""
        pathspec = ["--", ".", *(f":(exclude,literal){path}" for path in exclude)]
        names = self.git(
            ["diff", "--name-only", "-z", "--no-renames", before, after, *pathspec],
            deadline=deadline,
        )
        diff = self.git(
            ["diff", "--no-ext-diff", "--no-color", before, after, *pathspec],
            deadline=deadline,
            errors="replace",
        )
        return [name for name in names.split("\0") if name], diff.strip()

    def create_repository_baseline(
        self,
        before: str,
        after: Snapshot,
        repository: str,
        fork: str,
        deadline: float | None = None,
    ) -> str:
        """*before* with the repository at *repository* — a path *before*
        does not hold — as its own checkout of *fork* left it, judged by the
        repository itself: each file it reports unchanged since *fork* as it
        is in *after*, each file it reports changed as *fork*'s content in the
        form its checkout writes (its end-of-line and smudge filters applied),
        and no file *fork* lacks. The diff from it to *after* then shows what
        changed since *fork*, whatever those filters make of the bytes on disk
        — a checkout under `core.autocrlf` is CRLF where the commit is LF. A
        changed file *after* lacks counts as deleted only while the listing
        would still take it; one it leaves out now — ignored since, or under
        an ignored directory — stays out of both."""
        where = os.path.join(self._workdir, *repository.split("/"))
        changed = get_git_output(
            ["diff", "--name-only", "-z", "--no-renames", fork], where, deadline
        )
        changed_paths = {path for path in changed.split("\0") if path}
        forked = _tree_entries(
            get_git_output(["ls-tree", "-r", "-z", fork], where, deadline)
        )
        current = _tree_entries(
            self.git(
                ["ls-tree", "-r", "-z", after.tree, "--", repository],
                deadline=deadline,
            )
        )
        prefix = f"{repository}/"
        # Unchanged since *fork*: exactly as it is now, so it cannot read as
        # changed whatever the filters did to its bytes.
        entries = [
            f"{mode} {sha}\t{path}"
            for path, (mode, sha) in current.items()
            if path[len(prefix) :] in forked
            and path[len(prefix) :] not in changed_paths
        ]
        # Changed since *fork*. One *fork* lacks was added since: absent from
        # the baseline, it reads as added. A submodule is a repository of its
        # own, with its own baseline.
        existing = [
            rel
            for rel in sorted(changed_paths)
            if rel in forked and forked[rel][0] != _GITLINK_MODE
        ]
        # One *after* lacks was deleted — unless the listing leaves it out
        # now, which would make it read as deleted while it is still there.
        out_of_scope = get_out_of_scope_paths(
            self._workdir,
            [f"{prefix}{rel}" for rel in existing if f"{prefix}{rel}" not in current],
            list(after.repositories),
            self._ignore_dirs,
            self._exclude_paths,
            deadline,
        )
        for rel in existing:
            if f"{prefix}{rel}" not in out_of_scope:
                blob = self._hash_checkout(where, f"{fork}:{rel}", deadline)
                entries.append(f"{forked[rel][0]} {blob}\t{prefix}{rel}")
        return self._edit_tree(before, add=entries, deadline=deadline)

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
        argv, env = self._command(args, index, deadline)
        return run_git_command(
            argv, self._workdir, deadline, env, stdin, errors, f"git {args[0]}"
        )

    def _command(
        self, args: list[str], index: str | None, deadline: float | None
    ) -> tuple[list[str], dict[str, str]]:
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
        return argv, env

    def _hash_checkout(self, repository: str, blob: str, deadline: float | None) -> str:
        """Store *blob* of the repository at *repository* as its checkout
        writes it — `cat-file --filters` applies the repository's own
        filters — and return its SHA in the store."""
        content = run_git_binary(
            ["git", "cat-file", "--filters", blob], repository, deadline
        )
        if content.returncode != 0:
            error = content.stderr.decode("utf-8", "replace").strip()
            raise SnapshotError(f"git cat-file failed: {error}")
        argv, env = self._command(
            ["hash-object", "-w", "--stdin", "--no-filters"], None, deadline
        )
        stored = run_git_binary(
            argv, self._workdir, deadline, env, content.stdout, "git hash-object"
        )
        if stored.returncode != 0:
            error = stored.stderr.decode("utf-8", "replace").strip()
            raise SnapshotError(f"git hash-object failed: {error}")
        return stored.stdout.decode("ascii").strip()

    @contextmanager
    def _operation_index(self, from_cache: bool) -> Iterator[str]:
        """An index file for one operation. With *from_cache* it starts as a
        copy of the store's named index and replaces it when the operation
        succeeds; without, it starts empty and is discarded. It is deleted,
        with any lock a killed command left on it, however the operation
        ends."""
        index = f"{self.index}.{uuid.uuid4().hex}"
        if from_cache and os.path.exists(self.index):
            # With its timestamp: git re-hashes an entry as new as the index
            # file, which catches a file rewritten within the same second at
            # the same size. A fresh timestamp would vouch for its stat data.
            shutil.copy2(self.index, index)
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
    ) -> tuple[Listing, list[str]]:
        """Bring *index* to the directory's current listing; return the
        listing and the files git could not read."""
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
    ) -> list[str]:
        """Add *paths* to the index — `--remove` drops one deleted from disk —
        and return the ones left out because git could not read them.

        `update-index` gives up at the first unreadable file and names it, so
        that file is left out — its entry dropped, should the cached index
        hold an earlier version — and the rest are fed again; each rerun re-stats
        the others instead of hashing them. The file is found by matching each
        path against the end of git's output, not by parsing a path out of
        it: git prints the name raw, so a newline in it would split a parsed
        line."""
        remaining, unreadable = list(paths), []
        while remaining:
            result = self._update_index(
                ["--add", "--remove"], remaining, index, deadline
            )
            if result.returncode == 0:
                break
            failed = next(
                (
                    path
                    for path in remaining
                    if result.stderr.endswith(f"{_UNREADABLE_PREFIX}{path}\n")
                ),
                None,
            )
            if failed is None:
                raise SnapshotError(f"git update-index failed: {result.stderr.strip()}")
            remaining.remove(failed)
            unreadable.append(failed)
        if unreadable:
            # The cached index may still hold an earlier version of each; the
            # snapshot must hold nothing for them, not stale content.
            result = self._update_index(["--force-remove"], unreadable, index, deadline)
            if result.returncode != 0:
                raise SnapshotError(f"git update-index failed: {result.stderr.strip()}")
        return unreadable

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

    def _edit_tree(
        self,
        treeish: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
        deadline: float | None = None,
    ) -> str:
        """*treeish*'s tree with *add* — `update-index --index-info` entries,
        `<mode> <sha>\\t<path>` — put in and *remove*'s paths taken out."""
        with self._operation_index(from_cache=False) as index:
            self.git(["read-tree", treeish], index=index, deadline=deadline)
            if add:
                self.git(
                    ["update-index", "-z", "--index-info"],
                    index=index,
                    stdin="".join(f"{entry}\0" for entry in add),
                    deadline=deadline,
                )
            if remove:
                self.git(
                    ["update-index", "--force-remove", "-z", "--stdin"],
                    index=index,
                    stdin="".join(f"{path}\0" for path in remove),
                    deadline=deadline,
                )
            return self.git(["write-tree"], index=index, deadline=deadline).strip()


def _tree_entries(listing: str) -> dict[str, tuple[str, str]]:
    """`ls-tree -r -z` output as `{path: (mode, sha)}`."""
    entries: dict[str, tuple[str, str]] = {}
    for line in listing.split("\0"):
        meta, _, path = line.partition("\t")
        if path:
            mode, _, sha = meta.split(" ")
            entries[path] = (mode, sha)
    return entries


def _tree_paths(listing: str) -> list[str]:
    """`ls-tree -r -z --name-only` output as a list of paths."""
    return [path for path in listing.split("\0") if path]


def _index_entries(listing: str) -> dict[str, tuple[str, str]]:
    """`ls-files --stage -z` output as `{path: (mode, sha)}`."""
    entries: dict[str, tuple[str, str]] = {}
    for line in listing.split("\0"):
        meta, _, path = line.partition("\t")
        if path:
            mode, sha, _ = meta.split(" ")
            entries[path] = (mode, sha)
    return entries


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
