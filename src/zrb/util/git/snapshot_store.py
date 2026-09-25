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
- leaves out a file larger than `CFG.LLM_SNAPSHOT_FILE_MAX_MB` as if it were ignored — a
  dataset or build artifact nobody ignored would otherwise be copied into the
  store in full, and hashed again for as long as it keeps changing;
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
import unicodedata
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Iterator, NamedTuple

from zrb.config.config import CFG
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
# `FILE_ATTRIBUTE_REPARSE_POINT`: set on a Windows junction or symlink.
_REPARSE_POINT = 0x400


logger = logging.getLogger(__name__)


class Snapshot(NamedTuple):
    """A snapshot's tree, and what it knows about the directory that its tree
    cannot hold — which a restore needs to tell a file that did not exist
    then from one the snapshot never saw. Paths are relative to the work
    tree."""

    #: The snapshot's tree SHA.
    tree: str
    #: Files left out because git could not read them.
    unreadable: tuple[str, ...] = ()
    #: Every other path that existed but the tree does not hold, apart from
    #: `DEFAULT_IGNORE_DIRS` and the excluded paths: what each repository
    #: ignored, and the directories that could not be read. A directory ends
    #: in `/`.
    left_out: tuple[str, ...] = ()
    #: The repositories it listed; `""` is the work tree itself.
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
    def create_temporary(
        cls,
        workdir: str,
        reading_from: str | None = None,
        deadline: float | None = None,
    ) -> "SnapshotStore":
        """A new store in an owner-only temporary directory, borrowing the
        listed repositories' objects. `delete` it when done.

        With *reading_from*, another store's directory, it also reads that
        store's objects and starts from a copy of its stat cache, so it can
        diff against that store's trees — without ever writing to it."""
        store = cls(
            tempfile.mkdtemp(prefix="zrb-snapshot-"), workdir, borrow_objects=True
        )
        if reading_from is not None:
            try:
                store.ensure(deadline)
                _read_from(store, reading_from)
            except BaseException:
                store.delete()
                raise
        return store

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
        # Only when it differs, and by rename: another process's snapshot may be
        # hashing under these rules right now, and an attributes file seen
        # empty mid-rewrite would let the project's filters (git-lfs) in.
        _write_if_changed(os.path.join(info, "attributes"), _BYTE_EXACT_ATTRIBUTES)
        self._initialized = True

    def snapshot(self, deadline: float | None = None) -> Snapshot:
        """Snapshot the directory and write its tree. Raises
        `SnapshotBudgetError` when the directory holds too many files outside
        every repository."""
        with self._operation_index(from_cache=True) as index:
            listing, unreadable = self._index_directory(index, deadline)
            tree = self.git(["write-tree"], index=index, deadline=deadline).strip()
        # Sorted, so two snapshots of the same directory compare equal.
        return Snapshot(
            tree,
            tuple(sorted(unreadable)),
            tuple(sorted(listing.left_out)),
            tuple(sorted(listing.repositories)),
        )

    def restore(self, snapshot: Snapshot, deadline: float | None = None) -> list[str]:
        """Make the directory match *snapshot*, and return the paths it could
        not — empty when the directory now matches.

        Each path is decided by its state now (ADR-0101 has the table):

        - listed and readable: rewritten to the snapshot's version, or, when
          the snapshot lacks it, removed only if the snapshot shows it did
          not exist then;
        - unreadable, or under a directory that cannot be read: left alone —
          its content is in no snapshot, so writing over it is irreversible;
        - ignored or excluded: left alone;
        - absent: recreated from the snapshot.

        A write the filesystem refuses — a file another program holds open,
        a directory without write permission — does not stop the others: git
        writes every file it can, and the paths left behind are returned, so
        restoring again finishes once the cause is gone. A failure before the
        write raises, with nothing changed; one during it — a timeout — returns
        every path the restore meant to change, since the directory is then
        partly restored and restoring again finishes it."""
        with self._operation_index(from_cache=True) as index:
            listing, unreadable = self._index_directory(index, deadline)
            before = self.git(["write-tree"], index=index, deadline=deadline).strip()
            current = _index_entries(
                self.git(["ls-files", "--stage", "-z"], index=index, deadline=deadline)
            )
            target, in_the_way = self._create_restore_target(
                snapshot.tree, listing, unreadable, current, deadline
            )
            wanted = self._list_tree(target, deadline)
            lacking = self._find_lacking(current, set(wanted))
            created = set(_find_created_since(lacking, snapshot, listing.repositories))
            kept = [path for path in lacking if path not in created]
            # A kept file where the snapshot has a directory, or under a path
            # it has as a file: the tree cannot hold both, and the file stays.
            clashing = _find_clashes(wanted, kept)
            in_the_way |= clashing
            final = self._edit_tree(
                target,
                remove=sorted(clashing),
                add=[f"{current[path][0]} {current[path][1]}\t{path}" for path in kept],
                deadline=deadline,
            )
            meant = self._changed_paths(before, final, deadline)
            try:
                self._write_tree_to_disk(final, index, deadline)
                left_behind = self._find_left_behind(meant, final, index, deadline)
            except (SnapshotError, OSError) as e:
                logger.warning(f"Restore stopped partway: {e}")
                left_behind = meant
            return sorted(set(left_behind) | in_the_way)

    def _create_restore_target(
        self,
        treeish: str,
        listing: Listing,
        unreadable: list[str],
        current: dict[str, tuple[str, str]],
        deadline: float | None,
    ) -> tuple[str, set[str]]:
        """*treeish*'s tree minus every path a restore must leave alone —
        those out of scope now, the files git cannot read now, and, when not
        listed, the ones under a directory that cannot be read — and minus
        the paths something unlisted stands in the way of, which it also
        returns: they are left behind (`_find_in_the_way`)."""
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
        # `left_out` adds the files too large to snapshot: ignored ones are in
        # `out` already.
        left_alone = out | set(unreadable) | set(unseen) | set(listing.left_out)
        in_the_way = self._find_in_the_way(
            [path for path in paths if path not in left_alone], current
        )
        target = self._edit_tree(
            treeish, remove=sorted(left_alone | in_the_way), deadline=deadline
        )
        return target, in_the_way

    def _find_in_the_way(
        self, paths: list[str], current: dict[str, tuple[str, str]]
    ) -> set[str]:
        """The *paths* git could write only by destroying something no
        snapshot holds. `read-tree -u --reset` removes an untracked file or
        directory in the way of what it writes, and anything the operation
        index lacks is untracked to it: a directory holding an ignored file
        where the snapshot has a file or symlink, an ignored file or a FIFO
        where it has a file or needs a directory. A listed path in the way is
        the restore's own to replace, and so is a directory holding only
        listed files; a real directory above a path is not in its way."""
        listed = {_fold(path) for path in current}
        verdicts: dict[str, bool] = {}  # an ancestor: whether it blocks

        def is_in_the_way(rel: str, is_ancestor: bool) -> bool:
            if _fold(rel) in listed:
                return False
            try:
                info = os.lstat(self._absolute(rel))
            except (FileNotFoundError, NotADirectoryError):
                return False  # nothing there, or under a listed file
            except OSError:
                return True  # cannot tell: left alone
            if _is_real_directory(info):
                return not is_ancestor and self._has_unlisted(rel, listed)
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

    def _has_unlisted(self, rel: str, listed: set[str]) -> bool:
        """Whether the directory at *rel* holds anything the listing does
        not — or anything it cannot look into, which counts the same."""
        pending = [rel]
        while pending:
            directory = pending.pop()
            try:
                with os.scandir(self._absolute(directory)) as it:
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

    def _absolute(self, rel: str) -> str:
        return os.path.join(self._workdir, *rel.split("/"))

    def _find_lacking(
        self, current: dict[str, tuple[str, str]], wanted: set[str]
    ) -> list[str]:
        """The current paths the target lacks. On a filesystem that ignores
        letter case or Unicode normalization (macOS, Windows), a current path
        the target holds in another case or form is the same file: the
        target's version is written to it, and it is not lacking, so it is
        never removed as created since — which would delete that file."""
        missing = {_fold(path): path for path in wanted if path not in current}
        twins = {
            path
            for path in current
            if (twin := missing.get(_fold(path))) is not None
            and twin != path
            and os.path.lexists(self._absolute(twin))
        }
        return sorted(path for path in current if path not in wanted | twins)

    def _list_tree(self, treeish: str, deadline: float | None) -> list[str]:
        return _tree_paths(
            self.git(["ls-tree", "-r", "-z", "--name-only", treeish], deadline=deadline)
        )

    def _find_left_behind(
        self, meant: Iterable[str], final: str, index: str, deadline: float | None
    ) -> list[str]:
        """The paths of *meant*, the ones a restore meant to change, that the
        directory does not hold as *final* has them."""
        meant = set(meant)
        self._index_directory(index, deadline)
        actual = self.git(["write-tree"], index=index, deadline=deadline).strip()
        return [
            path
            for path in self._changed_paths(final, actual, deadline)
            if path in meant
        ]

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
        self, before: str, after: str, deadline: float | None = None
    ) -> tuple[list[str], str]:
        """The paths (relative to `work_tree`) that differ between two trees,
        and their unified diff.

        The paths are exact — NUL-separated, so git neither quotes an unusual
        name nor loses one to trimming — and without rename detection, so a
        renamed file's old path is listed too. The diff ignores the user's
        external diff tool and colour settings, and replaces undecodable bytes
        with U+FFFD: it goes to a model, which may reject lone surrogates."""
        diff = self.git(
            ["diff", "--no-ext-diff", "--no-color", before, after],
            deadline=deadline,
            errors="replace",
        )
        return self._changed_paths(before, after, deadline), diff.strip()

    def _changed_paths(
        self, before: str, after: str, deadline: float | None
    ) -> list[str]:
        names = self.git(
            ["diff", "--name-only", "-z", "--no-renames", before, after],
            deadline=deadline,
        )
        return [name for name in names.split("\0") if name]

    def create_tree_without(
        self, treeish: str, paths: Iterable[str], deadline: float | None = None
    ) -> str:
        """*treeish*'s tree with *paths* taken out."""
        return self._edit_tree(treeish, remove=sorted(paths), deadline=deadline)

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
        where = self._absolute(repository)
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
        filters — and return its SHA in the store. *blob* is
        `<commit>:<path>`, the form `--filters` requires: it names the path
        whose `.gitattributes` choose the filters as well as the blob."""
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
        try:
            if from_cache and os.path.exists(self.index):
                # With its timestamp: git re-hashes an entry as new as the
                # index file, which catches a file rewritten within the same
                # second at the same size. A fresh timestamp would vouch for
                # its stat data.
                shutil.copy2(self.index, index)
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
        listing = self._leave_out_large_files(
            list_snapshot_paths(
                self._workdir,
                self._ignore_dirs,
                self._exclude_paths,
                deadline,
            )
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

    def _leave_out_large_files(self, listing: Listing) -> Listing:
        """Move each listed file larger than `CFG.LLM_SNAPSHOT_FILE_MAX_MB` from
        *listing*'s paths to what it left out, where a restore treats it as it
        does an ignored file: never written over, never removed."""
        max_bytes = CFG.LLM_SNAPSHOT_FILE_MAX_MB * 2**20
        large: set[str] = set()
        for path in listing.paths:
            try:
                info = os.lstat(self._absolute(path))
            except OSError:
                continue  # gone or unreadable: the index step decides
            if stat.S_ISREG(info.st_mode) and info.st_size > max_bytes:
                large.add(path)
        if large:
            listing.paths = [path for path in listing.paths if path not in large]
            listing.left_out.extend(sorted(large))
        return listing

    def _add_readable(
        self, paths: list[str], index: str, deadline: float | None
    ) -> list[str]:
        """Add *paths* to the index — `--remove` drops one deleted from disk —
        and return the ones left out because they cannot be read.

        `update-index` stops at the first file it cannot read. Its message
        naming the file is not relied on — its wording differs between git
        versions and is translated into the user's language — so when a run
        fails, the unreadable files are found by opening each one, and the
        rest are fed again (a rerun re-stats the others rather than hashing
        them). A failure no unreadable file explains is raised. An
        unreadable file's entry is dropped too, should the cached index hold
        an earlier version: the snapshot must hold nothing for it, not stale
        content."""
        unreadable: list[str] = []
        remaining = list(paths)
        while True:
            result = self._update_index(
                ["--add", "--remove"], remaining, index, deadline
            )
            if result.returncode == 0:
                break
            newly_unreadable = [
                path for path in remaining if not self._is_readable(path)
            ]
            if not newly_unreadable:
                raise SnapshotError(f"git update-index failed: {result.stderr.strip()}")
            unreadable.extend(newly_unreadable)
            left_out = set(newly_unreadable)
            remaining = [path for path in remaining if path not in left_out]
        if unreadable:
            result = self._update_index(["--force-remove"], unreadable, index, deadline)
            if result.returncode != 0:
                raise SnapshotError(f"git update-index failed: {result.stderr.strip()}")
        return unreadable

    def _is_readable(self, path: str) -> bool:
        """Whether git can read *path* to hash it: a regular file it can
        open, a symlink (stored as its target's name), or a missing path
        (removed, not read). A FIFO, socket or device is none of these — git
        cannot store one — and is never opened: opening a FIFO blocks until
        something writes to it."""
        full = self._absolute(path)
        try:
            mode = os.lstat(full).st_mode
        except FileNotFoundError:
            return True
        except OSError:
            return False
        if stat.S_ISLNK(mode):
            return True
        if not stat.S_ISREG(mode):
            return False
        try:
            os.close(os.open(full, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)))
        except OSError:
            return False
        return True

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
    try:
        os.remove(path)
    except FileNotFoundError:
        pass  # never made, or removed already: gone either way


def _write(path: str, content: str) -> None:
    # LF on Windows too: git reads an `alternates` line ending in `\r` as a
    # path that does not exist.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def _write_if_changed(path: str, content: str) -> None:
    """Give *path* *content*, atomically, unless it already has it."""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            if f.read() == content:
                return
    except OSError:
        pass  # missing or unreadable: written below
    temporary = f"{path}.{uuid.uuid4().hex}"
    _write(temporary, content)
    os.replace(temporary, path)


def _read_from(store: SnapshotStore, other_git_dir: str) -> None:
    """Make *store* read *other_git_dir*'s objects, and start from a copy of
    its stat cache (with its timestamp: see `SnapshotStore._operation_index`)."""
    alternates = os.path.join(store.git_dir, "objects", "info", "alternates")
    os.makedirs(os.path.dirname(alternates), exist_ok=True)
    _write(alternates, os.path.join(os.path.realpath(other_git_dir), "objects") + "\n")
    other_index = os.path.join(other_git_dir, "index")
    if os.path.exists(other_index):
        shutil.copy2(other_index, store.index)


def _find_created_since(
    lacking: list[str], snapshot: Snapshot, repositories: list[str]
) -> list[str]:
    """The *lacking* files *snapshot* shows did not exist when it was taken:
    it would have listed them, since it neither left them out nor failed to
    read them. The files of a repository listed now (*repositories*) that it
    did not list are kept instead: a worktree or clone made since, whose own
    history holds its work.

    Left-out paths are matched ignoring case and Unicode normalization
    (`_fold`): on a filesystem that ignores them, `Build/` then is `build/`
    now, and elsewhere this keeps at most a file that differs from a
    left-out one only so. Repositories are
    matched exactly, which errs the same way — toward keeping."""
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
        # A left-out directory covers what its own repository would list
        # there, not a repository inside it, which listed itself.
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


def _find_clashes(wanted: list[str], kept: list[str]) -> set[str]:
    """The *wanted* paths a *kept* file stands in the way of: one under a
    kept file, or a file where a kept one needs a directory."""
    kept_files = {_fold(path) for path in kept}
    kept_directories = {parent for path in kept for parent in _parents(_fold(path))}
    return {
        path
        for path in wanted
        if _fold(path) in kept_directories
        or any(parent in kept_files for parent in _parents(_fold(path)))
    }


def _parents(path: str) -> list[str]:
    """`a/b/c` → `a`, `a/b`."""
    parts = path.split("/")
    return ["/".join(parts[:depth]) for depth in range(1, len(parts))]
