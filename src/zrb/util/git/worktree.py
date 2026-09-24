"""Snapshot a git working tree as a tree object, leaving the repository's own
index, HEAD and files untouched — so what changed between two moments (the
start and end of one agent turn) can be diffed, however it was changed.

Every function returns None when git is missing, the directory is not in a
repository, or a command fails: callers treat a snapshot as best-effort.
"""

import os
import shutil
import subprocess
import tempfile

_TIMEOUT_SECONDS = 30


def get_repo_root(cwd: str) -> str | None:
    """The top-level directory of the repository containing *cwd*."""
    return _run(["git", "rev-parse", "--show-toplevel"], cwd)


def snapshot_worktree(cwd: str) -> str | None:
    """The tree SHA of the working tree of *cwd*'s repository — tracked and
    untracked files, `.gitignore` honoured.

    Built through a throwaway index, so the real index, HEAD and files are
    untouched. File contents do land in the object store as loose blobs,
    which `git gc` prunes once nothing references them.
    """
    root = get_repo_root(cwd)
    if root is None:
        return None
    scratch = tempfile.mkdtemp(prefix="zrb-worktree-")
    try:
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(scratch, "index")}
        if _run(["git", "add", "-A"], root, env) is None:
            return None
        return _run(["git", "write-tree"], root, env)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def diff_snapshots(cwd: str, before: str, after: str) -> tuple[list[str], str] | None:
    """The repo-relative paths that differ between two `snapshot_worktree`
    trees, and their unified diff."""
    names = _run(["git", "diff", "--name-only", before, after], cwd)
    if names is None:
        return None
    diff = _run(["git", "diff", before, after], cwd)
    if diff is None:
        return None
    return [name for name in names.splitlines() if name], diff


def _run(args: list[str], cwd: str, env: dict[str, str] | None = None) -> str | None:
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()
