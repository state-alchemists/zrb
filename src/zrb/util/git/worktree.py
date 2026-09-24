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
    index = env["GIT_INDEX_FILE"]
    if os.path.exists(index):
        os.remove(index)
    if _run(["git", "add", "-A"], root, env, deadline) is None:
        return None
    return _run(["git", "write-tree"], root, env, deadline)


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
) -> str | None:
    timeout = get_command_timeout(deadline)
    if timeout <= 0:
        return None
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()
