"""Git-backed snapshot manager for LLM rewind functionality.

Snapshots are commits in a private git directory with the project as its
work tree — nothing is copied. One git directory serves every session of a
project, at ``<snapshot_dir>/<name>-<hash of its path>.git``, so unchanged
files are stored once; each session has its own ref
(``refs/zrb/<session>-<hash>``) and its own index, so concurrent sessions
never share a lock. A session is keyed by its name and the workdir's path
inside the work tree; the hashes keep two paths or names that sanitize alike
from sharing a store or a history.

Git's ignore rules apply: files the project's ``.gitignore`` excludes are
neither snapshotted nor touched by a restore — including a file that became
ignored after an earlier snapshot captured it. When the workdir is inside a git
repository, the work tree is the repository root and every git command is
limited to the workdir, so ``.gitignore`` files above the workdir apply too.

Snapshot flow: ``git add -A`` into the session's index, ``write-tree``,
``commit-tree``, ``update-ref``.

Restore flow: filter now-ignored paths out of ``<sha>``'s tree, ``git add -A``
(so files created since are in the index), then ``read-tree -u --reset`` to
the filtered tree — which rewrites changed files, recreates deleted ones and
removes the rest — then move the session ref back to ``<sha>``.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import subprocess
from typing import Callable, NamedTuple

from zrb.util.git.worktree import get_repo_root, untrack_ignored
from zrb.util.string.conversion import to_safe_filename

logger = logging.getLogger(__name__)

# A local git process can still hang on lock contention, a corrupted repo, or
# a slow disk. Every subprocess.run in this module gets this bound so a stall
# here is a bounded wait, not a silent, unrecoverable freeze.
_GIT_TIMEOUT_SECONDS = 30

# `git add --ignore-errors` exits 1 when it skipped a file it could not index
# (permission denied, a nested repository with no commit) and added the rest.
_ADD_PARTIAL_EXIT = 1

_IDENTITY_ENV = {
    "GIT_AUTHOR_NAME": "zrb-snapshot",
    "GIT_AUTHOR_EMAIL": "zrb-snapshot@local",
    "GIT_COMMITTER_NAME": "zrb-snapshot",
    "GIT_COMMITTER_EMAIL": "zrb-snapshot@local",
}


# Progress callback contract for `take_init_snapshot`. Stages:
#   "start"      right before the working tree is hashed
#   "done"       init commit exists; skipped counts files git could not index
#   "up-to-date" session already has snapshots (resumed session)
#   "error"      failed after "start"; reason carries the exception text
# All events fire on the event-loop thread: each report happens in coroutine
# context, before or after an `await asyncio.to_thread(...)` returns.
class SnapshotProgress(NamedTuple):
    """Progress event for `take_init_snapshot` (see `SnapshotProgressFn`)."""

    stage: str
    skipped: int = 0
    reason: str = ""


SnapshotProgressFn = Callable[[SnapshotProgress], None]


class Snapshot(NamedTuple):
    sha: str
    timestamp: str
    label: str
    message_count: int | None = None


class SnapshotManager:
    """Manages filesystem snapshots in a private git directory."""

    # Directories that are large, regenerable, and almost never contain
    # hand-edited content, excluded even where no `.gitignore` names them
    # (a workdir outside git). Never snapshotted, never touched by restore.
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

    def __init__(
        self,
        snapshot_dir: str,
        session_name: str,
        workdir: str,
        ignore_dirs: "frozenset[str] | set[str] | None" = None,
    ):
        self._snapshot_dir = snapshot_dir
        self._workdir = os.path.abspath(workdir)
        self._session_name = session_name
        self._session = ""
        self._ref = ""
        self._ignore_dirs: frozenset[str] = (
            self.DEFAULT_IGNORE_DIRS if ignore_dirs is None else frozenset(ignore_dirs)
        )
        self._git_dir = ""
        self._work_tree = ""
        self._pathspec = "."
        self._initialized = False
        # Serializes snapshots and restores: they share this session's index.
        self._lock = asyncio.Lock()

    async def take_snapshot(
        self, label: str, message_count: int | None = None
    ) -> str | None:
        """Snapshot the workdir and commit.  Returns commit SHA or None on error.

        Args:
            label: Human-readable label (typically the user message).
            message_count: Number of conversation messages at this point.  When
                provided it is embedded in the commit message so that restore can
                also rewind the conversation history to a consistent state.
        """
        try:
            async with self._lock:
                sha, _ = await asyncio.to_thread(self._commit, label, message_count)
                return sha
        except Exception as e:
            logger.warning(f"Snapshot failed: {e}")
            return None

    async def take_init_snapshot(
        self, on_progress: SnapshotProgressFn | None = None
    ) -> str | None:
        """Take a baseline snapshot at session start.

        Always creates a commit (even if workdir is empty) so that
        list_snapshots() always has at least one entry to rewind to.

        Args:
            on_progress: Optional callback; see `SnapshotProgressFn` for the
                event contract. Every invocation ends with exactly one
                terminal event ("done", "up-to-date", or "error").
        """
        started = False
        try:
            async with self._lock:
                await asyncio.to_thread(self._ensure_initialized)
                existing_sha = await asyncio.to_thread(self._head_sha)
                if existing_sha is not None:
                    _report_progress(on_progress, SnapshotProgress("up-to-date"))
                    return existing_sha
                started = True
                _report_progress(on_progress, SnapshotProgress("start"))
                sha, skipped = await asyncio.to_thread(self._commit, "init", 0)
            _report_progress(on_progress, SnapshotProgress("done", skipped))
            return sha
        except Exception as e:
            logger.warning(f"Init snapshot failed: {e}")
            if started:
                _report_progress(on_progress, SnapshotProgress("error", reason=str(e)))
            return None

    def list_snapshots(self) -> list[Snapshot]:
        """Return snapshots in reverse chronological order (newest first)."""
        try:
            self._ensure_initialized()
            if self._head_sha() is None:
                return []
            log = self._git(["log", "--format=%H|%ai|%s", self._ref])
            snapshots: list[Snapshot] = []
            for line in log.splitlines():
                parts = line.split("|", 2)
                if len(parts) == 3:
                    label, message_count = _parse_commit_message(parts[2])
                    snapshots.append(
                        Snapshot(
                            sha=parts[0],
                            timestamp=parts[1],
                            label=label,
                            message_count=message_count,
                        )
                    )
            return snapshots
        except Exception as e:
            logger.warning(f"list_snapshots failed: {e}")
            return []

    async def restore_snapshot(self, sha: str) -> bool:
        """Restore workdir to the state captured at the given snapshot SHA."""
        try:
            async with self._lock:
                await asyncio.to_thread(self._restore, sha)
            return True
        except Exception as e:
            logger.warning(f"restore_snapshot failed: {e}")
            return False

    def _ensure_initialized(self):
        if self._initialized:
            return
        repo_root = get_repo_root(self._workdir)
        self._work_tree = os.path.realpath(repo_root or self._workdir)
        rel = os.path.relpath(os.path.realpath(self._workdir), self._work_tree)
        self._pathspec = "." if rel == "." else rel
        # A session resumed from another directory of the same repository
        # gets its own history and index: restoring a snapshot taken in one
        # directory must not delete files the other never snapshotted.
        self._session = _readable_key(
            self._session_name, f"{self._session_name}\0{rel}"
        )
        self._ref = f"refs/zrb/{self._session}"
        store = _readable_key(os.path.basename(self._work_tree), self._work_tree)
        self._git_dir = os.path.join(self._snapshot_dir, f"{store}.git")
        if not os.path.isdir(os.path.join(self._git_dir, "objects")):
            os.makedirs(self._git_dir, exist_ok=True)
            result = _run(["git", "init", "-q", "--bare", self._git_dir])
            if result.returncode != 0:
                raise RuntimeError(f"git init failed: {result.stderr.strip()}")
        exclude = "".join(f"{d}/\n" for d in sorted(self._ignore_dirs))
        info_dir = os.path.join(self._git_dir, "info")
        os.makedirs(info_dir, exist_ok=True)
        with open(os.path.join(info_dir, "exclude"), "w", encoding="utf-8") as f:
            f.write(exclude)
        self._initialized = True

    def _commit(self, label: str, message_count: int | None) -> tuple[str, int]:
        """Commit the workdir unless it matches HEAD; return (sha, skipped)."""
        self._ensure_initialized()
        skipped = self._add_all()
        tree = self._git(["write-tree"])
        head = self._head_sha()
        if head is not None:
            head_tree, head_subject = self._git(
                ["log", "-1", "--format=%T%n%s", head]
            ).split("\n", 1)
            # A new commit is still needed when only message_count advanced
            # (e.g. after a rewind followed by turns that don't touch the FS):
            # restore reads mc from the commit, so a stale one would truncate
            # conversation history to the wrong point.
            _, head_mc = _parse_commit_message(head_subject)
            if head_tree == tree and (
                message_count is None or head_mc == message_count
            ):
                return head, skipped
        parent = ["-p", head] if head else []
        message = _build_commit_message(label, message_count)
        sha = self._git(["commit-tree", "--no-gpg-sign", tree, *parent, "-m", message])
        self._git(["update-ref", self._ref, sha])
        return sha, skipped

    def _restore(self, sha: str) -> None:
        self._ensure_initialized()
        self._git(["cat-file", "-e", f"{sha}^{{commit}}"])
        tree = self._tree_without_ignored(sha)
        self._add_all()
        self._git(["read-tree", "-u", "--reset", tree])
        self._git(["update-ref", self._ref, sha])

    def _tree_without_ignored(self, sha: str) -> str:
        """*sha*'s tree minus the paths git ignores now, so a restore neither
        overwrites nor recreates a file that became ignored since."""
        index = self._index + ".restore"
        try:
            self._git(["read-tree", sha], index)
            untrack_ignored(self._runner(index))
            return self._git(["write-tree"], index)
        finally:
            if os.path.exists(index):
                os.remove(index)

    def _add_all(self) -> int:
        """Stage the workdir; return how many files git could not index."""
        result = self._run_git(["add", "-A", "--ignore-errors", "--", self._pathspec])
        if result.returncode not in (0, _ADD_PARTIAL_EXIT):
            raise RuntimeError(result.stderr.strip())
        untrack_ignored(self._runner(self._index))
        skipped = [
            line
            for line in result.stderr.splitlines()
            if line.startswith("error: unable to index file")
            or line.endswith("does not have a commit checked out")
        ]
        for line in skipped:
            logger.debug(f"Snapshot skipped: {line}")
        return len(skipped)

    def _head_sha(self) -> str | None:
        result = self._run_git(["rev-parse", "--verify", "-q", self._ref])
        return result.stdout.strip() if result.returncode == 0 else None

    @property
    def _index(self) -> str:
        return os.path.join(self._git_dir, f"index-{self._session}")

    def _git(self, args: list[str], index: str | None = None) -> str:
        result = self._run_git(args, index)
        if result.returncode != 0:
            raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def _runner(self, index: str) -> Callable[..., str | None]:
        """A `untrack_ignored` runner: `git ...` against *index*."""

        def run(args: list[str], stdin: str | None = None) -> str | None:
            result = self._run_git(args[1:], index, stdin)
            return result.stdout if result.returncode == 0 else None

        return run

    def _run_git(
        self, args: list[str], index: str | None = None, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            **_IDENTITY_ENV,
            "GIT_INDEX_FILE": index or self._index,
        }
        return _run(
            ["git", f"--git-dir={self._git_dir}", f"--work-tree={self._work_tree}"]
            + args,
            cwd=self._work_tree,
            env=env,
            stdin=stdin,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_MC_TAG = "[mc:"  # message-count tag embedded in commit messages


def _build_commit_message(label: str, message_count: int | None) -> str:
    if message_count is None:
        return label
    return f"{label} {_MC_TAG}{message_count}]"


def _parse_commit_message(raw: str) -> tuple[str, int | None]:
    """Return (human_label, message_count).  message_count is None if not present."""

    m = re.search(r"\[mc:(\d+)\]$", raw)
    if m:
        return raw[: m.start()].rstrip(), int(m.group(1))
    return raw, None


def _readable_key(name: str, identity: str) -> str:
    """*name* made filename- and ref-safe, plus a hash of *identity*: the
    sanitized name alone collides (`a:b` and `a?b` both become `a_b`)."""
    digest = hashlib.sha256(identity.encode("utf-8", "surrogateescape")).hexdigest()
    return f"{to_safe_filename(name)[:40]}-{digest[:16]}"


def _run(
    args: list[str],
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_SECONDS,
    )


def _report_progress(
    on_progress: "SnapshotProgressFn | None", event: SnapshotProgress
) -> None:
    """Invoke a progress callback, never letting it break the snapshot."""
    if on_progress is None:
        return
    try:
        on_progress(event)
    except Exception as e:
        logger.debug(f"Snapshot progress callback failed: {e}")
