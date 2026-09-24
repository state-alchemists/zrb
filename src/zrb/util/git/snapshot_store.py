"""Snapshots of a directory as git trees, kept in a private bare repository.

The directory is the repository's work tree: nothing is copied, and nothing is
written into the directory or into a git repository it belongs to. `/rewind`
(`llm/snapshot/manager.py`) commits these trees into a persistent store; the
self-review gate diffs two of them from a per-turn temporary store.

Inside a git repository the work tree is the repository's root and every
command is limited to the directory, so the repository's `.gitignore` files —
above the directory too — and its `info/exclude` apply. Outside one, the
directory itself is the work tree and `DEFAULT_IGNORE_DIRS` keeps regenerable
caches out. Either way a snapshot:

- honours the ignore rules as they are now, even for a path an earlier
  snapshot captured (`git add -A` alone never untracks one);
- stores bytes exactly: the store's `info/attributes`, which outranks the
  project's `.gitattributes`, disables line-ending and encoding conversion and
  clean/smudge filters, so a restore cannot rewrite a file or write git-lfs
  pointer files into the directory;
- skips a file git cannot read, or a nested repository with no commit, rather
  than failing, and reports how many it skipped;
- never snapshots the store itself, wherever it lies.

Every git command is bounded: by `GIT_COMMAND_TIMEOUT_SECONDS`, and by an
optional *deadline* (a `time.monotonic()` value) that cuts off a whole
sequence of commands. Failures raise `SnapshotError`.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Iterable, TypeVar

#: The most one git command may take, deadline or not.
GIT_COMMAND_TIMEOUT_SECONDS = 30

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

_BYTE_EXACT_ATTRIBUTES = "* -text -filter -ident -working-tree-encoding\n"

# `git add --ignore-errors` exits 1 when it skipped a file it could not index
# and added the rest.
_ADD_PARTIAL_EXIT = 1

# Inherited variables that would point git at another repository, index or
# object database than the one each command names.
_REDIRECTING_ENV = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
)

_IDENTITY_ENV = {
    "GIT_AUTHOR_NAME": "zrb-snapshot",
    "GIT_AUTHOR_EMAIL": "zrb-snapshot@local",
    "GIT_COMMITTER_NAME": "zrb-snapshot",
    "GIT_COMMITTER_EMAIL": "zrb-snapshot@local",
}

# Set in the worker thread running a snapshot operation when the coroutine
# awaiting it is cancelled; `SnapshotStore.run_git` stops at the next command.
_worker = threading.local()

_T = TypeVar("_T")


class SnapshotError(RuntimeError):
    """A snapshot git command failed, timed out, or was cancelled."""


def get_repo_root(cwd: str, deadline: float | None = None) -> str | None:
    """The top-level directory of the git repository containing *cwd*, or
    None outside one (or when git is unavailable)."""
    try:
        return _run(["git", "rev-parse", "--show-toplevel"], cwd, deadline).strip()
    except SnapshotError:
        return None


def get_command_timeout(deadline: float | None) -> float:
    """Seconds the next git command may take: `GIT_COMMAND_TIMEOUT_SECONDS`,
    or less when *deadline* is nearer. Zero or below means no time is left."""
    if deadline is None:
        return GIT_COMMAND_TIMEOUT_SECONDS
    return min(GIT_COMMAND_TIMEOUT_SECONDS, deadline - time.monotonic())


async def run_in_worker(fn: Callable[..., _T], *args: Any) -> _T:
    """Run *fn* in a worker thread; when the caller is cancelled, stop it
    before its next git command and wait for it before the cancellation
    propagates.

    Cancelling cannot stop a thread. A caller holding a lock around a snapshot
    would otherwise release it while git still runs, letting the next
    operation race the same index — or a cancelled commit move a history
    forward after a later rewind."""
    abort = threading.Event()

    def work() -> _T:
        _worker.abort = abort
        try:
            return fn(*args)
        finally:
            _worker.abort = None

    future = asyncio.ensure_future(asyncio.to_thread(work))
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        abort.set()
        await asyncio.wait([future])
        raise


class SnapshotStore:
    """A private bare repository whose work tree is *workdir* (or the root of
    the git repository containing it).

    *index_name* names this user's index inside the store, so several can
    share one store without sharing a lock. *exclude_paths* are further
    absolute paths never to snapshot. With *borrow_objects*, the store reads
    the enclosing repository's objects as an alternate instead of storing its
    own copy of every tracked file — only for a short-lived store, since the
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
        self._exclude_paths = [os.path.realpath(p) for p in exclude_paths]
        self._borrow_objects = borrow_objects
        self._work_tree = ""
        self._pathspec = "."
        self._initialized = False

    @classmethod
    def create_temporary(cls, workdir: str) -> "SnapshotStore":
        """A new store in an owner-only temporary directory, borrowing the
        enclosing repository's objects. `delete` it when done."""
        return cls(
            tempfile.mkdtemp(prefix="zrb-snapshot-"), workdir, borrow_objects=True
        )

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
        """The work tree's root; snapshot paths are relative to it."""
        self.ensure()
        return self._work_tree

    @property
    def pathspec(self) -> str:
        """The snapshotted directory relative to `work_tree` (`.` for all)."""
        self.ensure()
        return self._pathspec

    def delete(self) -> None:
        """Remove the store and every object its snapshots wrote.

        Git writes object files read-only, which Windows refuses to delete, so
        each one refused is made writable and removed again — a store left
        behind would keep copies of untracked files, secrets included.

        Safe to call more than once, and on a store that was never created:
        cleanup paths race, and a second delete must not mask the error that
        triggered the first. The error handler also absorbs the store
        vanishing between the check below and `rmtree`."""
        if not os.path.isdir(self._git_dir):
            return
        if sys.version_info >= (3, 12):
            shutil.rmtree(self._git_dir, onexc=_remove_read_only)
        else:
            shutil.rmtree(
                self._git_dir,
                onerror=lambda fn, path, _info: _remove_read_only(fn, path, None),
            )

    def ensure(self, deadline: float | None = None) -> None:
        """Create the store if needed and (re)write its ignore and attribute
        rules. Raises SnapshotError when git cannot set it up."""
        if self._initialized:
            return
        repo_root = get_repo_root(self._workdir, deadline)
        self._work_tree = os.path.realpath(repo_root or self._workdir)
        rel = os.path.relpath(self._workdir, self._work_tree)
        self._pathspec = "." if rel == "." else rel
        if not os.path.isdir(os.path.join(self._git_dir, "objects")):
            os.makedirs(self._git_dir, exist_ok=True)
            _run(["git", "init", "-q", "--bare", self._git_dir], None, deadline)
        info = os.path.join(self._git_dir, "info")
        os.makedirs(info, exist_ok=True)
        _write(os.path.join(info, "exclude"), self._exclude_rules(repo_root, deadline))
        _write(os.path.join(info, "attributes"), _BYTE_EXACT_ATTRIBUTES)
        if self._borrow_objects and repo_root is not None:
            objects = _run(
                ["git", "rev-parse", "--git-path", "objects"], self._workdir, deadline
            ).strip()
            alternates = os.path.join(self._git_dir, "objects", "info", "alternates")
            os.makedirs(os.path.dirname(alternates), exist_ok=True)
            _write(alternates, os.path.join(self._workdir, objects) + "\n")
        self._initialized = True

    def snapshot(self, deadline: float | None = None) -> tuple[str, int]:
        """Snapshot the directory; return its tree SHA and how many files git
        could not index. The index persists, so unchanged files are skipped
        by stat on the next snapshot instead of being hashed again."""
        self.ensure(deadline)
        result = self.run_git(
            ["add", "-A", "--ignore-errors", "--", self._pathspec], deadline=deadline
        )
        if result.returncode not in (0, _ADD_PARTIAL_EXIT):
            raise SnapshotError(f"git add failed: {result.stderr.strip()}")
        skipped = sum(
            1
            for line in result.stderr.splitlines()
            if line.startswith("error: unable to index file")
            or line.endswith("does not have a commit checked out")
        )
        self.untrack_ignored(deadline=deadline)
        return self.git(["write-tree"], deadline=deadline).strip(), skipped

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

    def untrack_ignored(
        self, index: str | None = None, deadline: float | None = None
    ) -> None:
        """Drop from *index* (the store's own by default) every path git now
        ignores."""
        ignored = self.git(
            ["ls-files", "-z", "--cached", "--ignored", "--exclude-standard"],
            index=index,
            deadline=deadline,
        )
        if ignored:
            # Literal paths, and no up-to-date check: `rm --cached` refuses an
            # entry that differs from both the file and HEAD, as a restore's does.
            self.git(
                ["update-index", "--force-remove", "-z", "--stdin"],
                index=index,
                stdin=ignored,
                deadline=deadline,
            )

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
        abort = getattr(_worker, "abort", None)
        if abort is not None and abort.is_set():
            raise SnapshotError(f"Snapshot cancelled before running git {args[0]}")
        self.ensure(deadline)
        env = {**_clean_env(), **_IDENTITY_ENV, "GIT_INDEX_FILE": index or self.index}
        argv = [
            "git",
            # A global `core.fsmonitor` would start a watcher daemon per store.
            "-c",
            "core.fsmonitor=false",
            f"--git-dir={self._git_dir}",
            f"--work-tree={self._work_tree}",
            *args,
        ]
        return _complete(argv, self._work_tree, deadline, env, stdin, errors)

    def _exclude_rules(self, repo_root: str | None, deadline: float | None) -> str:
        rules = [f"{d}/" for d in sorted(self._ignore_dirs)]
        if repo_root is not None:
            # The repository's own `info/exclude`: this store's replaces it.
            exclude = _run(
                ["git", "rev-parse", "--git-path", "info/exclude"],
                self._workdir,
                deadline,
            ).strip()
            try:
                with open(os.path.join(self._workdir, exclude), encoding="utf-8") as f:
                    rules.append(f.read())
            except OSError:
                pass
        for path in [self._git_dir, *self._exclude_paths]:
            rel = _relpath_inside(path, self._work_tree)
            if rel is not None:
                rules.append(f"{_anchored_pattern(rel)}/")
        return "".join(f"{rule.rstrip()}\n" for rule in rules if rule.strip())


def _relpath_inside(path: str, root: str) -> str | None:
    """*path* relative to *root* when it lies strictly inside it, else None."""
    try:
        rel = os.path.relpath(path, root)
    except ValueError:  # another drive on Windows: never inside
        return None
    if rel == "." or rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return None
    return rel


def _anchored_pattern(rel_path: str) -> str:
    """A gitignore pattern matching exactly *rel_path* under the work tree."""
    escaped = re.sub(r"([\\*?\[])", r"\\\1", rel_path.replace(os.sep, "/"))
    stripped = escaped.rstrip(" ")
    return "/" + stripped + "\\ " * (len(escaped) - len(stripped))


def _remove_read_only(fn: Callable[[str], Any], path: str, _exc: Any) -> None:
    """`rmtree` error handler: retry a refused removal once it is writable,
    and ignore what still fails (a store is deleted best-effort)."""
    try:
        os.chmod(path, stat.S_IWRITE)
        fn(path)
    except OSError:
        pass


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _REDIRECTING_ENV}


def _run(args: list[str], cwd: str | None, deadline: float | None) -> str:
    result = _complete(args, cwd, deadline, _clean_env())
    if result.returncode != 0:
        raise SnapshotError(f"git {args[1]} failed: {result.stderr.strip()}")
    return result.stdout


def _complete(
    argv: list[str],
    cwd: str | None,
    deadline: float | None,
    env: dict[str, str],
    stdin: str | None = None,
    errors: str = "surrogateescape",
) -> subprocess.CompletedProcess[str]:
    """Run *argv* within the deadline. Output is UTF-8 whatever the locale:
    `surrogateescape` keeps a non-UTF-8 file name's bytes intact, and
    re-encodes them the same way on stdin."""
    timeout = get_command_timeout(deadline)
    if timeout <= 0:
        raise SnapshotError(f"No time left to run {' '.join(argv[:2])}")
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            input=stdin,
            capture_output=True,
            encoding="utf-8",
            errors=errors,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise SnapshotError(
            f"{' '.join(argv[:2])} timed out after {timeout:.0f}s"
        ) from e
    except OSError as e:
        raise SnapshotError(f"Could not run git: {e}") from e
