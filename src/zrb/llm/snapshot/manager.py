"""Git-backed snapshot manager for LLM rewind functionality.

Snapshots are commits of `SnapshotStore` trees (`util/git/snapshot_store.py`)
— the working directory is the store's work tree, so nothing is copied, and
the store's listing, byte-exactness and self-exclusion rules apply: every
repository under the directory by its own ignore rules, nested ones included,
and the loose files outside them up to a budget.

Layout: one store per working directory, at ``<snapshot_dir>/<name>-<hash of
its path>.git``, so unchanged files are stored once and one stat cache serves
every conversation there; one ref per conversation, ``refs/zrb/<name>-<hash>``,
keyed by the conversation's name — the identity its chat history is saved and
resumed under — since a snapshot records that conversation's message count.
The manager follows the conversation the UI is on: `/load` switches to that
conversation's history, and `/save` copies the current one to the new name.
The hashes keep two paths or names that sanitize alike from sharing a store
or a history. The store keeps its own objects — rewind history outlives the
session, and borrowing a repository's could lose a blob to a `git gc` there.

Snapshot flow: snapshot the directory, ``commit-tree``, ``update-ref``. A
commit names the files git could not read, as a trailer.

Restore flow: refuse a commit outside this conversation's history, then
`SnapshotStore.restore` — which rewrites changed files, recreates deleted
ones and removes files created since, never one the snapshot left out for
being ignored or unreadable, nor a repository made since, and never writing
over a file it cannot read now — then move the conversation's ref back to
``<sha>``. The outcome names every path a refused write left behind.

Rewind turns itself off for the session, with a reason the first snapshot
and `/rewind` show, when the directory cannot be snapshotted at all: a
snapshot directory that is the working directory itself, a store that cannot
be set up — its directory not writable, git not installed — or more loose
files outside any repository than the listing's budget. Later operations do
not retry.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import threading
from typing import Callable, NamedTuple

from zrb.util.git.snapshot_command import SnapshotError, run_in_worker
from zrb.util.git.snapshot_listing import DEFAULT_IGNORE_DIRS, SnapshotBudgetError
from zrb.util.git.snapshot_store import SnapshotStore
from zrb.util.string.conversion import to_safe_filename

logger = logging.getLogger(__name__)


# Progress callback contract for `take_init_snapshot`. Stages:
#   "start"      right before the working tree is hashed
#   "done"       init commit exists; skipped counts files git could not read
#   "up-to-date" session already has snapshots (resumed session)
#   "error"      the snapshot failed, with or without a "start" before it;
#                reason is `unavailable_reason` when rewind is off for the
#                session, else the failure's text
# Every invocation ends with exactly one of the last three. All events fire on
# the event-loop thread: each report happens in coroutine context, before or
# after an awaited worker returns.
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


class RestoreOutcome(NamedTuple):
    """What `restore_snapshot` did."""

    #: Whether the restore ran. False: nothing was touched — an unknown
    #: commit, one outside this conversation's history, or rewind is off.
    restored: bool
    #: Paths the restore could not bring back although it ran — a file
    #: another program holds open, a directory without write permission.
    #: Every other file is restored; restoring again finishes the job once
    #: the cause is gone.
    left_behind: tuple[str, ...] = ()


class SnapshotManager:
    """Manages filesystem snapshots in a private git directory.

    Rewind history belongs to a conversation. *session_name* names the one
    the manager is on, or is a callable returning the current name — a UI
    passes one, so rewind follows `/load` and `/save`. Each operation reads
    the name once, when it starts, so a switch never lands half an operation
    in the wrong conversation."""

    #: Never snapshotted, never touched by restore, even inside a repository.
    DEFAULT_IGNORE_DIRS: frozenset[str] = DEFAULT_IGNORE_DIRS

    def __init__(
        self,
        snapshot_dir: str,
        session_name: "str | Callable[[], str]",
        workdir: str,
        ignore_dirs: "frozenset[str] | set[str] | None" = None,
    ):
        self._snapshot_dir = os.path.realpath(snapshot_dir)
        self._workdir = os.path.realpath(workdir)
        self._session_name = session_name
        self._ignore_dirs: frozenset[str] = (
            self.DEFAULT_IGNORE_DIRS if ignore_dirs is None else frozenset(ignore_dirs)
        )
        self._store: SnapshotStore | None = None
        self._store_lock = threading.Lock()
        self._unavailable = _check_location(self._snapshot_dir, self._workdir)
        # Serializes this process's snapshots, restores and history copies.
        self._lock = asyncio.Lock()

    @property
    def session_name(self) -> str:
        """The conversation whose rewind history operations use now."""
        name = self._session_name
        return name() if callable(name) else name

    @session_name.setter
    def session_name(self, value: str) -> None:
        self._session_name = value

    @property
    def unavailable_reason(self) -> str:
        """Why rewind is off for this session, or empty (see the module
        docstring for when)."""
        return self._unavailable

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
        session = self.session_name
        try:
            async with self._lock:
                sha, _ = await run_in_worker(
                    self._commit, session, label, message_count
                )
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
        if self._unavailable:
            _report_progress(
                on_progress, SnapshotProgress("error", reason=self._unavailable)
            )
            return None
        session = self.session_name
        try:
            async with self._lock:
                existing_sha = await run_in_worker(self._head_sha, session)
                if existing_sha is not None:
                    _report_progress(on_progress, SnapshotProgress("up-to-date"))
                    return existing_sha
                _report_progress(on_progress, SnapshotProgress("start"))
                sha, skipped = await run_in_worker(self._commit, session, "init", 0)
            _report_progress(on_progress, SnapshotProgress("done", skipped))
            return sha
        except Exception as e:
            self._note_unavailable(e)
            logger.warning(f"Init snapshot failed: {e}")
            reason = self._unavailable or str(e)
            _report_progress(on_progress, SnapshotProgress("error", reason=reason))
            return None

    def list_snapshots(self) -> list[Snapshot]:
        """Return the current conversation's snapshots, newest first."""
        if self._unavailable:
            return []
        session = self.session_name
        try:
            if self._head_sha(session) is None:
                return []
            log = self._get_store().git(["log", "--format=%H|%ai|%s", _ref(session)])
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
            self._note_unavailable(e)
            logger.warning(f"list_snapshots failed: {e}")
            return []

    async def restore_snapshot(self, sha: str) -> RestoreOutcome:
        """Restore workdir to the state captured at the given snapshot SHA."""
        if self._unavailable:
            return RestoreOutcome(restored=False)
        session = self.session_name
        try:
            async with self._lock:
                left_behind = await run_in_worker(self._restore, session, sha)
            return RestoreOutcome(restored=True, left_behind=tuple(left_behind))
        except Exception as e:
            self._note_unavailable(e)
            logger.warning(f"restore_snapshot failed: {e}")
            return RestoreOutcome(restored=False)

    async def copy_history(self, source: str, target: str) -> None:
        """Give conversation *target* the rewind history of *source* — what
        saving a conversation under a new name does to its chat history —
        replacing any it had. A *source* with no snapshots leaves *target*
        with none: its old ones would carry message counts of a chat
        history that no longer exists."""
        if self._unavailable or source == target:
            return
        try:
            async with self._lock:
                await run_in_worker(self._copy_history, source, target)
        except Exception as e:
            self._note_unavailable(e)
            logger.warning(f"Copying rewind history failed: {e}")

    def _note_unavailable(self, error: Exception) -> None:
        """Turn rewind off for the session when *error* will not pass by
        itself: the directory is over the listing's budget. (A store that
        cannot be set up turns it off in `_get_store`.)"""
        if isinstance(error, SnapshotBudgetError):
            self._unavailable = str(error)

    def _get_store(self) -> SnapshotStore:
        """The working directory's store, set up on first use. A failure to
        set it up — its directory not writable, git not installed, a location
        the store refuses — will not pass by itself, so it turns rewind off
        for the session with its reason."""
        with self._store_lock:
            if self._store is not None:
                return self._store
            name = _readable_key(os.path.basename(self._workdir), self._workdir)
            git_dir = os.path.join(self._snapshot_dir, f"{name}.git")
            try:
                store = SnapshotStore(
                    git_dir,
                    self._workdir,
                    ignore_dirs=self._ignore_dirs,
                    # A snapshot dir inside the directory holds other
                    # directories' stores too; none of it belongs in a
                    # snapshot.
                    exclude_paths=[self._snapshot_dir],
                )
                store.ensure()
            except (OSError, ValueError, SnapshotError) as e:
                self._unavailable = f"the snapshot store {git_dir} is unusable: {e}"
                raise SnapshotError(self._unavailable) from e
            self._store = store
            return store

    def _commit(
        self, session: str, label: str, message_count: int | None
    ) -> tuple[str, int]:
        """Commit the workdir unless it matches HEAD; return the SHA and how
        many files git could not read."""
        store = self._get_store()
        tree, unreadable, _ = store.snapshot()
        skipped = len(unreadable)
        head = self._head_sha(session)
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
        message = _build_commit_message(label, message_count, unreadable)
        sha = store.git(
            ["commit-tree", "--no-gpg-sign", tree, *parent, "-m", message]
        ).strip()
        store.git(["update-ref", _ref(session), sha])
        return sha, skipped

    def _restore(self, session: str, sha: str) -> list[str]:
        """Restore *sha*, move the conversation's ref back to it, and return
        the paths left behind."""
        store = self._get_store()
        store.git(["cat-file", "-e", f"{sha}^{{commit}}"])
        # Only this conversation's own snapshots: another conversation's
        # commit in the same store is not in this one's list, so restoring it
        # would rewind the files without rewinding the conversation to match.
        ancestry = store.run_git(["merge-base", "--is-ancestor", sha, _ref(session)])
        if ancestry.returncode:
            raise SnapshotError(f"{sha} is not one of this conversation's snapshots")
        body = store.git(["log", "-1", "--format=%B", sha])
        left_behind = store.restore(sha, keep=_parse_unreadable(body))
        store.git(["update-ref", _ref(session), sha])
        return left_behind

    def _copy_history(self, source: str, target: str) -> None:
        store = self._get_store()
        head = self._head_sha(source)
        if head is not None:
            store.git(["update-ref", _ref(target), head])
        elif self._head_sha(target) is not None:
            store.git(["update-ref", "-d", _ref(target)])

    def _head_sha(self, session: str) -> str | None:
        result = self._get_store().run_git(
            ["rev-parse", "--verify", "-q", _ref(session)]
        )
        return result.stdout.strip() if result.returncode == 0 else None


def _check_location(snapshot_dir: str, workdir: str) -> str:
    """Why *snapshot_dir* cannot serve *workdir*, or empty. Stores are
    direct children of *snapshot_dir*, so they lie inside *workdir* only when
    *snapshot_dir* does. Inside it, the whole snapshot directory is left out
    of every snapshot; equal to it, that would leave out everything."""
    if snapshot_dir == workdir:
        return (
            f"the snapshot directory is the working directory itself "
            f"({workdir}); set LLM_SNAPSHOT_DIR elsewhere"
        )
    return ""


def _ref(session: str) -> str:
    """Conversation *session*'s history."""
    return f"refs/zrb/{_readable_key(session, session)}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_MC_TAG = "[mc:"  # message-count tag embedded in commit messages
# Trailer naming, as JSON, the files a snapshot could not read: a restore
# must not remove them for being absent from it.
_UNREADABLE_TRAILER = "zrb-unreadable: "


def _build_commit_message(
    label: str, message_count: int | None, unreadable: tuple[str, ...] = ()
) -> str:
    subject = label if message_count is None else f"{label} {_MC_TAG}{message_count}]"
    if not unreadable:
        return subject
    return f"{subject}\n\n{_UNREADABLE_TRAILER}{json.dumps(list(unreadable))}"


def _parse_unreadable(body: str) -> list[str]:
    for line in body.splitlines():
        if line.startswith(_UNREADABLE_TRAILER):
            return json.loads(line[len(_UNREADABLE_TRAILER) :])
    return []


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
