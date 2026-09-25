"""Git-backed snapshot manager for LLM rewind functionality.

Snapshots are commits of `SnapshotStore` trees (`util/git/snapshot_store.py`)
— the working directory is the store's work tree, so nothing is copied, and
the store's listing, byte-exactness and self-exclusion rules apply: every
repository under the directory by its own ignore rules, nested ones included,
and the loose files outside them up to a budget. One store serves every
conversation in a directory, at ``<snapshot_dir>/<name>-<hash of its
path>.git``, so unchanged files are stored once; each conversation has its
own ref (``refs/zrb/<session>-<hash>``) and index cache, keyed by its name —
the identity its chat history is saved and resumed under — since a snapshot
records that conversation's message count. The hashes keep two paths or
names that sanitize alike from sharing a store or a history. The store keeps its own objects — rewind
history outlives the session, and borrowing a repository's could lose a blob
to a `git gc` there.

Snapshot flow: snapshot into the session's index, ``commit-tree``,
``update-ref``.

Restore flow: refuse a commit outside this session's history, then
`SnapshotStore.restore` — which rewrites changed files, recreates deleted
ones and removes the rest, leaving alone any path the listing leaves out now
— then move the session ref back to ``<sha>``.

A directory over the listing's budget of loose files turns rewind off for
the session: the first snapshot reports why, and later ones do not walk the
directory again.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from typing import Callable, NamedTuple

from zrb.util.git.snapshot_command import SnapshotError, run_in_worker
from zrb.util.git.snapshot_listing import DEFAULT_IGNORE_DIRS, SnapshotBudgetError
from zrb.util.git.snapshot_store import SnapshotStore
from zrb.util.string.conversion import to_safe_filename

logger = logging.getLogger(__name__)


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

    #: Never snapshotted, never touched by restore, even inside a repository.
    DEFAULT_IGNORE_DIRS: frozenset[str] = DEFAULT_IGNORE_DIRS

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
        self._ignore_dirs: frozenset[str] = (
            self.DEFAULT_IGNORE_DIRS if ignore_dirs is None else frozenset(ignore_dirs)
        )
        self._ref = ""
        self._store: SnapshotStore | None = None
        # Why this directory cannot be snapshotted at all, once known.
        self._unavailable = ""
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
        if self._unavailable:
            return None
        try:
            async with self._lock:
                sha, _ = await run_in_worker(self._commit, label, message_count)
                return sha
        except Exception as e:
            self._note_unavailable(e)
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
                existing_sha = await run_in_worker(self._head_sha)
                if existing_sha is not None:
                    _report_progress(on_progress, SnapshotProgress("up-to-date"))
                    return existing_sha
                started = True
                _report_progress(on_progress, SnapshotProgress("start"))
                sha, skipped = await run_in_worker(self._commit, "init", 0)
            _report_progress(on_progress, SnapshotProgress("done", skipped))
            return sha
        except Exception as e:
            self._note_unavailable(e)
            logger.warning(f"Init snapshot failed: {e}")
            if started:
                _report_progress(on_progress, SnapshotProgress("error", reason=str(e)))
            return None

    def list_snapshots(self) -> list[Snapshot]:
        """Return snapshots in reverse chronological order (newest first)."""
        try:
            if self._head_sha() is None:
                return []
            log = self._get_store().git(["log", "--format=%H|%ai|%s", self._ref])
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
                await run_in_worker(self._restore, sha)
            return True
        except Exception as e:
            logger.warning(f"restore_snapshot failed: {e}")
            return False

    def _note_unavailable(self, error: Exception) -> None:
        if isinstance(error, SnapshotBudgetError):
            self._unavailable = str(error)

    def _get_store(self) -> SnapshotStore:
        if self._store is not None:
            return self._store
        workdir = os.path.realpath(self._workdir)
        session = _readable_key(self._session_name, self._session_name)
        self._ref = f"refs/zrb/{session}"
        name = _readable_key(os.path.basename(workdir), workdir)
        snapshot_dir = os.path.realpath(self._snapshot_dir)
        store = SnapshotStore(
            os.path.join(snapshot_dir, f"{name}.git"),
            workdir,
            index_name=f"index-{session}",
            ignore_dirs=self._ignore_dirs,
            # A snapshot dir inside the directory holds other directories'
            # stores too; none of it belongs in a snapshot.
            exclude_paths=[snapshot_dir],
        )
        store.ensure()
        self._store = store
        return store

    def _commit(self, label: str, message_count: int | None) -> tuple[str, int]:
        """Commit the workdir unless it matches HEAD; return (sha, skipped)."""
        store = self._get_store()
        tree, skipped, _ = store.snapshot()
        head = self._head_sha()
        if head is not None:
            head_tree, head_subject = (
                store.git(["log", "-1", "--format=%T%n%s", head]).strip().split("\n", 1)
            )
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
        sha = store.git(
            ["commit-tree", "--no-gpg-sign", tree, *parent, "-m", message]
        ).strip()
        store.git(["update-ref", self._ref, sha])
        return sha, skipped

    def _restore(self, sha: str) -> None:
        store = self._get_store()
        store.git(["cat-file", "-e", f"{sha}^{{commit}}"])
        # Only this session's own snapshots: another session's commit in the
        # same store is not in this conversation's list, so restoring it would
        # rewind the files without rewinding the conversation to match.
        if store.run_git(["merge-base", "--is-ancestor", sha, self._ref]).returncode:
            raise SnapshotError(f"{sha} is not one of this session's snapshots")
        store.restore(sha)
        store.git(["update-ref", self._ref, sha])

    def _head_sha(self) -> str | None:
        store = self._get_store()
        result = store.run_git(["rev-parse", "--verify", "-q", self._ref])
        return result.stdout.strip() if result.returncode == 0 else None


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
