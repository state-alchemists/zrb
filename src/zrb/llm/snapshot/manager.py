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
commit's message records what the snapshot knows that its tree cannot hold —
the files it could not read, the paths it left out, the repositories it
listed — and a restore rebuilds the snapshot from it.

Restore flow: refuse a commit outside this conversation's history, then
`SnapshotStore.restore` — which rewrites changed files, recreates deleted
ones and removes only the files the snapshot shows did not exist then, never
a repository made since, and never writing over a file it cannot read now —
then move the conversation's ref back to ``<sha>``. The outcome names every
path a refused write left behind.

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
from contextlib import contextmanager
from typing import Any, Callable, Iterator, NamedTuple, TypeVar

from zrb.util.file_lock import FileLockTimeout, hold_file_lock
from zrb.util.git.snapshot_command import (
    SnapshotError,
    SnapshotTimeoutError,
    run_in_worker,
)
from zrb.util.git.snapshot_listing import DEFAULT_IGNORE_DIRS, SnapshotBudgetError
from zrb.util.git.snapshot_store import Snapshot as StoreSnapshot
from zrb.util.git.snapshot_store import SnapshotStore
from zrb.util.string.conversion import to_safe_filename

logger = logging.getLogger(__name__)

#: The file in a rewind store whose OS lock every operation on it holds.
OPERATION_LOCK_NAME = "zrb-operation.lock"
#: The longest an operation waits for another to release the store. A store
#: still busy past it — another process stuck mid-restore — fails that one
#: operation, not the session's rewind.
STORE_LOCK_TIMEOUT_SECONDS = 60

_T = TypeVar("_T")


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
    """Progress event for `take_init_snapshot` (see `SnapshotProgressFn`).
    Read its fields by name: which ones it has is not fixed."""

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
    """What `restore_snapshot` did. True when the restore ran, as the bool
    `restore_snapshot` once returned was — a tuple is otherwise always true,
    and `if await manager.restore_snapshot(sha):` would pass on a failure."""

    #: Whether the restore ran. False: nothing was touched — an unknown
    #: commit, one outside this conversation's history, or rewind is off.
    restored: bool
    #: Paths the restore could not bring back although it ran — a file
    #: another program holds open, a directory without write permission.
    #: Every other file is restored; restoring again finishes the job once
    #: the cause is gone.
    left_behind: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.restored


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
        # target conversation -> source, recorded by `copy_history`, applied
        # by the next locked operation before anything else it does.
        self._pending_copies: dict[str, str] = {}
        self._pending_lock = threading.Lock()
        self._unavailable = _check_location(self._snapshot_dir, self._workdir)
        # Orders this manager's snapshots, restores and history copies.
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
                    self._run_locked, self._commit, session, label, message_count
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
                existing_sha = await run_in_worker(
                    self._run_locked, self._head_sha, session
                )
                if existing_sha is not None:
                    _report_progress(on_progress, SnapshotProgress("up-to-date"))
                    return existing_sha
                _report_progress(on_progress, SnapshotProgress("start"))
                sha, skipped = await run_in_worker(
                    self._run_locked, self._commit, session, "init", 0
                )
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
        session = self._visible_history(self.session_name)
        try:
            # Unlocked, and never setting a store up: either would hold the UI
            # up behind another operation. It needs no lock — the ref is read
            # once, and the commits it names never change.
            store = self._find_store_to_read()
            head = None if store is None else _read_head(store, session)
            if store is None or head is None:
                return []
            log = store.git(["log", "--format=%H|%ai|%s", head])
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
                left_behind = await run_in_worker(
                    self._run_locked, self._restore, session, sha
                )
            return RestoreOutcome(restored=True, left_behind=tuple(left_behind))
        except Exception as e:
            self._note_unavailable(e)
            logger.warning(f"restore_snapshot failed: {e}")
            return RestoreOutcome(restored=False)

    def copy_history(self, source: str, target: str) -> None:
        """Give conversation *target* the rewind history *source* has now —
        what saving a conversation under a new name does to its chat history
        — replacing any it had. A *source* with no snapshots leaves *target*
        with none: its old ones would carry message counts of a chat history
        that no longer exists.

        The copy is recorded at once and applied by the next operation that
        holds the manager's lock, before anything else that operation does,
        so no snapshot of either conversation can come between the save and
        the copy. Until then `list_snapshots` shows *target* the history it
        is about to receive."""
        if self._unavailable or source == target:
            return
        with self._pending_lock:
            # A copy of a copy not applied yet takes the original source.
            self._pending_copies[target] = self._pending_copies.get(source, source)

    def _note_unavailable(self, error: Exception) -> None:
        """Turn rewind off for the session when *error* will not pass by
        itself: the directory is over the listing's budget, or too large for
        a git command to hash within its time limit — retrying would hold
        every turn up for that long again. (A store that cannot be set up
        turns it off in `_get_store`.)"""
        if isinstance(error, SnapshotBudgetError):
            self._unavailable = str(error)
        elif isinstance(error, SnapshotTimeoutError):
            self._unavailable = (
                f"{self._workdir} is too large to snapshot in time ({error})"
            )

    def _get_store(self) -> SnapshotStore:
        """The working directory's store, set up on first use. A failure to
        set it up — its directory not writable, git not installed, a location
        the store refuses — will not pass by itself, so it turns rewind off
        for the session with its reason. It is set up holding the operation
        lock: two processes running `git init` on one directory at once fail
        on each other's config lock."""
        with self._store_lock:
            if self._store is not None:
                return self._store
            git_dir = self._store_git_dir()
            try:
                store = self._create_store_object(git_dir)
                os.makedirs(git_dir, mode=0o700, exist_ok=True)  # holds the lock
                with _hold_operation_lock(store):
                    store.ensure()
            except _StoreBusy:
                raise
            except (OSError, ValueError, SnapshotError) as e:
                self._unavailable = f"the snapshot store {git_dir} is unusable: {e}"
                raise SnapshotError(self._unavailable) from e
            self._store = store
            return store

    def _store_git_dir(self) -> str:
        name = _readable_key(os.path.basename(self._workdir), self._workdir)
        return os.path.join(self._snapshot_dir, f"{name}.git")

    def _create_store_object(self, git_dir: str) -> SnapshotStore:
        """The store at *git_dir*, not yet set up."""
        return SnapshotStore(
            git_dir,
            self._workdir,
            ignore_dirs=self._ignore_dirs,
            # A snapshot dir inside the directory holds other directories'
            # stores too; none of it belongs in a snapshot.
            exclude_paths=[self._snapshot_dir],
        )

    def _find_store_to_read(self) -> SnapshotStore | None:
        """The store as it is, set up or not, or None when there is none —
        so listing never sets one up, which waits for the operation lock."""
        if self._store is not None:
            return self._store
        git_dir = self._store_git_dir()
        if not os.path.isdir(os.path.join(git_dir, "objects")):
            return None
        return self._create_store_object(git_dir)

    def _apply_pending_copies(self) -> None:
        """Apply the copies `copy_history` recorded, in the order it recorded
        them. Called first by every locked operation (`_run_locked`), so each
        copy lands before anything that could build on either side."""
        with self._pending_lock:
            for target, source in self._pending_copies.items():
                self._copy_history(source, target)
            self._pending_copies.clear()

    def _visible_history(self, session: str) -> str:
        """The conversation whose history *session*'s list shows: the source
        of a copy to *session* not applied yet, else *session*."""
        with self._pending_lock:
            return self._pending_copies.get(session, session)

    def _run_locked(self, operation: Callable[..., _T], *args: Any) -> _T:
        """Run *operation* on the store holding its operation lock, after the
        copies `copy_history` recorded. `self._lock` orders this manager's
        operations; the lock on a file in the store keeps every other one off
        it too — another conversation's manager in this process, another
        process — so a restore never interleaves with another restore, and a
        snapshot never catches one half-written. The OS releases it when its
        holder dies."""
        with _hold_operation_lock(self._get_store()):
            self._apply_pending_copies()
            return operation(*args)

    def _commit(
        self, session: str, label: str, message_count: int | None
    ) -> tuple[str, int]:
        """Commit the workdir unless it matches HEAD; return the SHA and how
        many files git could not read."""
        store = self._get_store()
        snapshot = store.snapshot()
        skipped = len(snapshot.unreadable)
        head = self._head_sha(session)
        if head is not None:
            head_snapshot, head_subject = self._read_commit(head)
            # A new commit is still needed when only message_count advanced
            # (e.g. after a rewind followed by turns that don't touch the FS):
            # restore reads mc from the commit, so a stale one would truncate
            # conversation history to the wrong point. So is one when only the
            # record changed — a file ignored since HEAD was taken — or a
            # rewind to this point could remove that file.
            _, head_mc = _parse_commit_message(head_subject)
            if head_snapshot == snapshot and (
                message_count is None or head_mc == message_count
            ):
                return head, skipped
        parent = ["-p", head] if head else []
        message = _build_commit_message(label, message_count, snapshot)
        # The message on stdin: it names every path the snapshot left out,
        # which could exceed a command-line argument's limit.
        sha = store.git(
            ["commit-tree", "--no-gpg-sign", snapshot.tree, *parent], stdin=message
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
        snapshot, _ = self._read_commit(sha)
        if snapshot is None:
            # Without it a restore cannot tell a file that did not exist then
            # from one the snapshot never saw.
            raise SnapshotError(f"{sha} has no readable record of what it left out")
        left_behind = store.restore(snapshot)
        try:
            store.git(["update-ref", _ref(session), sha])
        except SnapshotError as e:
            # The files are restored either way; the list just keeps the
            # snapshots taken after *sha*.
            logger.warning(f"Could not move {session}'s rewind history back: {e}")
        return left_behind

    def _read_commit(self, sha: str) -> tuple[StoreSnapshot | None, str]:
        """The snapshot a commit records (None when its record is missing or
        malformed) and the commit's subject."""
        tree, _, message = (
            self._get_store().git(["log", "-1", "--format=%T%n%B", sha]).partition("\n")
        )
        return _parse_record(tree, message), message.partition("\n")[0]

    def _copy_history(self, source: str, target: str) -> None:
        store = self._get_store()
        head = self._head_sha(source)
        if head is not None:
            store.git(["update-ref", _ref(target), head])
        elif self._head_sha(target) is not None:
            store.git(["update-ref", "-d", _ref(target)])

    def _head_sha(self, session: str) -> str | None:
        return _read_head(self._get_store(), session)


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


class _StoreBusy(SnapshotError):
    """Another operation held the store past `STORE_LOCK_TIMEOUT_SECONDS`."""


@contextmanager
def _hold_operation_lock(store: SnapshotStore) -> Iterator[None]:
    path = os.path.join(store.git_dir, OPERATION_LOCK_NAME)
    try:
        with hold_file_lock(path, STORE_LOCK_TIMEOUT_SECONDS):
            yield
    except FileLockTimeout as e:
        raise _StoreBusy(f"the snapshot store is busy: {e}") from e


def _read_head(store: SnapshotStore, session: str) -> str | None:
    """The newest snapshot of *session*'s history in *store*, if any."""
    result = store.run_git(["rev-parse", "--verify", "-q", _ref(session)])
    return result.stdout.strip() if result.returncode == 0 else None


def _ref(session: str) -> str:
    """Conversation *session*'s history."""
    return f"refs/zrb/{_readable_key(session, session)}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# A snapshot's commit message. The label is the user's text, so the format
# gives it no way to pass for metadata:
#
#     <label, on one line> [mc:<message count, or ->]
#
#     zrb-snapshot: {"unreadable": [...], "left_out": [...], "repositories": [...]}
#
# The subject is one line, so no label can start a body line; the count tag
# is always written, so no label can end with one of its own; and the record
# is read from the body alone. It is written again with every commit: tens of
# KB for a repository with thousands of scattered ignored files.
_RECORD_TAG = "zrb-snapshot: "
_RECORD_FIELDS = ("unreadable", "left_out", "repositories")
_COUNT_TAG = re.compile(r" \[mc:(\d+|-)\]$")


def _build_commit_message(
    label: str, message_count: int | None, snapshot: StoreSnapshot
) -> str:
    one_line = " ".join(label.splitlines())
    count = "-" if message_count is None else str(message_count)
    record = {name: list(getattr(snapshot, name)) for name in _RECORD_FIELDS}
    return f"{one_line} [mc:{count}]\n\n{_RECORD_TAG}{json.dumps(record)}"


def _parse_commit_message(subject: str) -> tuple[str, int | None]:
    """A commit subject's label and message count (None when it has none)."""
    match = _COUNT_TAG.search(subject)
    if match is None:
        return subject, None
    count = match.group(1)
    return subject[: match.start()], None if count == "-" else int(count)


def _parse_record(tree: str, message: str) -> StoreSnapshot | None:
    """The snapshot of *tree* a commit message records — read from its body,
    never its subject — or None when the record is missing or malformed."""
    _, _, body = message.partition("\n")
    line = next(
        (line for line in body.splitlines() if line.startswith(_RECORD_TAG)), ""
    )
    try:
        record = json.loads(line[len(_RECORD_TAG) :])
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    fields: dict[str, tuple[str, ...]] = {}
    for name in _RECORD_FIELDS:
        paths = record.get(name)
        if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
            return None
        fields[name] = tuple(paths)
    return StoreSnapshot(tree.strip(), **fields)


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
