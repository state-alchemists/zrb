"""Snapshot a git working tree as a tree object without writing anything into
the repository — so what changed between two moments (the start and end of one
agent turn) can be diffed, however it was changed.

Snapshots live in a private *store*: an owner-only temporary directory holding
the throwaway index and every object a snapshot creates. The repository's own
objects are read through it as an alternate, never written, so the contents of
untracked files (a `.env`, a private key) never reach `.git/objects`. Delete
the store with `delete_snapshot_store` once its snapshots are no longer needed.

Every function returns None when git is missing, the directory is not in a
repository, or a command fails: callers treat a snapshot as best-effort. Each
also takes an optional *deadline* (a `time.monotonic()` value): every git
command it runs is cut off there — the child process killed — so a caller can
bound a whole sequence of commands, not just each one.
"""

import os
import shutil
import subprocess
import tempfile
import time
from typing import Callable

#: The most one git command may take, deadline or not.
GIT_COMMAND_TIMEOUT_SECONDS = 30


def get_repo_root(cwd: str, deadline: float | None = None) -> str | None:
    """The top-level directory of the repository containing *cwd*."""
    return _run(["git", "rev-parse", "--show-toplevel"], cwd, deadline=deadline)


def get_command_timeout(deadline: float | None) -> float:
    """Seconds the next git command may take: `GIT_COMMAND_TIMEOUT_SECONDS`,
    or less when *deadline* is nearer. Zero or below means no time is left."""
    if deadline is None:
        return GIT_COMMAND_TIMEOUT_SECONDS
    return min(GIT_COMMAND_TIMEOUT_SECONDS, deadline - time.monotonic())


def create_snapshot_store() -> str:
    """A new owner-only directory to hold snapshots' index and objects."""
    store = tempfile.mkdtemp(prefix="zrb-snapshot-")
    os.makedirs(os.path.join(store, "objects"))
    return store


def delete_snapshot_store(store: str) -> None:
    """Remove *store* and every object its snapshots wrote."""
    shutil.rmtree(store, ignore_errors=True)


def snapshot_worktree(
    cwd: str, store: str, deadline: float | None = None
) -> str | None:
    """The tree SHA of the working tree of *cwd*'s repository — tracked and
    untracked files, `.gitignore` honoured — with every object it creates
    written into *store*, and the repository's index, HEAD, files and object
    database untouched."""
    root = get_repo_root(cwd, deadline)
    if root is None:
        return None
    env = _store_env(root, store, deadline)
    if env is None:
        return None
    # The store's index persists between its snapshots, so unchanged files
    # are skipped by stat instead of re-hashed. A file git cannot index (no
    # permission, a nested repository with no commit) is left out rather than
    # failing the whole snapshot.
    add = ["git", "add", "-A", "--ignore-errors"]
    if _run(add, root, env, deadline, ok_codes=(0, 1)) is None:
        return None

    def run(args: list[str], stdin: str | None = None) -> str | None:
        # Unstripped: -z output may name a file beginning with a space.
        return _run(args, root, env, deadline, stdin=stdin, strip=False)

    try:
        untrack_ignored(run)
    except RuntimeError:
        return None
    return _run(["git", "write-tree"], root, env, deadline)


def untrack_ignored(run: Callable[..., str | None]) -> None:
    """Drop from the index every path git now ignores.

    `git add -A` never untracks a path already in the index, so a file that
    became ignored after an earlier snapshot would stay in every later one.
    *run* executes a git command against the private index — never the
    repository's — returning its stdout, or None on failure; it takes the
    command's stdin as `stdin`. Raises RuntimeError when a command fails."""
    ignored = run(
        ["git", "ls-files", "-z", "--cached", "--ignored", "--exclude-standard"]
    )
    if ignored is None:
        raise RuntimeError(
            "git ls-files failed listing ignored paths in the snapshot index"
        )
    if not ignored:
        return
    # Literal paths, and no up-to-date check: `rm --cached` refuses an entry
    # that differs from both the file and HEAD, which a restore's is.
    untrack = ["git", "update-index", "--force-remove", "-z", "--stdin"]
    if run(untrack, stdin=ignored) is None:
        raise RuntimeError(
            "git update-index failed removing ignored paths from the snapshot index"
        )


def diff_snapshots(
    cwd: str, store: str, before: str, after: str, deadline: float | None = None
) -> tuple[list[str], str] | None:
    """The repo-relative paths that differ between two snapshots taken into
    *store*, and their unified diff."""
    env = _store_env(cwd, store, deadline)
    if env is None:
        return None
    names = _run(["git", "diff", "--name-only", before, after], cwd, env, deadline)
    if names is None:
        return None
    diff = _run(["git", "diff", before, after], cwd, env, deadline)
    if diff is None:
        return None
    return [name for name in names.splitlines() if name], diff


def _store_env(cwd: str, store: str, deadline: float | None) -> dict[str, str] | None:
    """Git environment that reads the repository's objects and writes new ones
    into *store* only."""
    objects = _run(
        ["git", "rev-parse", "--git-path", "objects"], cwd, deadline=deadline
    )
    if objects is None:
        return None
    return {
        **os.environ,
        "GIT_INDEX_FILE": os.path.join(store, "index"),
        "GIT_OBJECT_DIRECTORY": os.path.join(store, "objects"),
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": os.path.abspath(os.path.join(cwd, objects)),
    }


def _run(
    args: list[str],
    cwd: str,
    env: dict[str, str] | None = None,
    deadline: float | None = None,
    ok_codes: tuple[int, ...] = (0,),
    stdin: str | None = None,
    strip: bool = True,
) -> str | None:
    timeout = get_command_timeout(deadline)
    if timeout <= 0:
        return None
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode not in ok_codes:
        return None
    return completed.stdout.strip() if strip else completed.stdout
