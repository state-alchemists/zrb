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
records that conversation's message count. The manager follows the
conversation the UI is on: `/load` switches to that conversation's history,
and `/save` copies the current one to the new name. The hashes keep two
paths or names that sanitize alike from sharing a store or a history. The
store keeps its own objects — rewind history outlives the session, and
borrowing a repository's could lose a blob to a `git gc` there.

Snapshot flow: snapshot into the conversation's index cache, ``commit-tree``,
``update-ref``. A commit names the files git could not read, as a trailer.

Restore flow: refuse a commit outside this conversation's history, then
`SnapshotStore.restore` — which rewrites changed files, recreates deleted
ones and removes files created since, never one the snapshot left out for
being ignored or unreadable, nor a repository made since — then move the
conversation's ref back to ``<sha>``.

A directory the store cannot snapshot — more loose files than the listing's
budget, or a snapshot directory that is the working directory itself — turns
rewind off for the session: the first snapshot and `/rewind` say why, and
later snapshots do not walk the directory again.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
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
#   "done"       init commit exists; skipped counts files git could not read
#   "up-to-date" session already has snapshots (resumed session)
#   "error"      failed after "start", reason carrying the exception text; or,
#                with no "start", rewind is off for the session and reason says
#                why (`unavailable_reason`)
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
    """Manages filesystem snapshots in a private git directory.

    Rewind history belongs to a conversation. *session_name* names the one
    the manager is on, or is a callable returning the current name — a UI
    passes one, so rewind follows `/load` and `/save`. Each operation resolves
    that conversation's history when it starts, so a switch never lands half
    an operation in the wrong one."""

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
        self._histories: dict[str, _History] = {}
        self._unavailable = ""
        if self._snapshot_dir == self._workdir:
            # Other directories' stores would land in this one and be
            # snapshotted with it.
            self._unavailable = (
                f"the snapshot directory is the working directory itself "
                f"({self._workdir}); set LLM_SNAPSHOT_DIR elsewhere"
            )
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
        """Why this directory cannot be snapshotted at all, or empty: a
        snapshot directory that is the working directory itself, or more
        loose files outside any repository than the listing's budget."""
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
        started = False
        try:
            async with self._lock:
                existing_sha = await run_in_worker(self._head_sha, session)
                if existing_sha is not None:
                    _report_progress(on_progress, SnapshotProgress("up-to-date"))
                    return existing_sha
                started = True
                _report_progress(on_progress, SnapshotProgress("start"))
                sha, skipped = await run_in_worker(self._commit, session, "init", 0)
            _report_progress(on_progress, SnapshotProgress("done", skipped))
            return sha
        except Exception as e:
            self._note_unavailable(e)
            logger.warning(f"Init snapshot failed: {e}")
            if started:
                _report_progress(on_progress, SnapshotProgress("error", reason=str(e)))
            return None

    def list_snapshots(self) -> list[Snapshot]:
        """Return the current conversation's snapshots, newest first."""
        if self._unavailable:
            return []
        session = self.session_name
        try:
            if self._head_sha(session) is None:
                return []
            history = self._history(session)
            log = history.store.git(["log", "--format=%H|%ai|%s", history.ref])
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
        if self._unavailable:
            return False
        session = self.session_name
        try:
            async with self._lock:
                await run_in_worker(self._restore, session, sha)
            return True
        except Exception as e:
            logger.warning(f"restore_snapshot failed: {e}")
            return False

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
            logger.warning(f"Copying rewind history failed: {e}")

    def _note_unavailable(self, error: Exception) -> None:
        if isinstance(error, SnapshotBudgetError):
            self._unavailable = str(error)

    def _history(self, session: str) -> "_History":
        """Conversation *session*'s history: its ref, and a store handle with
        its own index cache, all in the directory's one store."""
        history = self._histories.get(session)
        if history is not None:
            return history
        key = _readable_key(session, session)
        name = _readable_key(os.path.basename(self._workdir), self._workdir)
        store = SnapshotStore(
            os.path.join(self._snapshot_dir, f"{name}.git"),
            self._workdir,
            index_name=f"index-{key}",
            ignore_dirs=self._ignore_dirs,
            # A snapshot dir inside the directory holds other directories'
            # stores too; none of it belongs in a snapshot.
            exclude_paths=[self._snapshot_dir],
        )
        store.ensure()
        history = _History(store, f"refs/zrb/{key}")
        self._histories[session] = history
        return history

    def _commit(
        self, session: str, label: str, message_count: int | None
    ) -> tuple[str, int]:
        """Commit the workdir unless it matches HEAD; return the SHA and how
        many files git could not read."""
        store, ref = self._history(session)
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
        store.git(["update-ref", ref, sha])
        return sha, skipped

    def _restore(self, session: str, sha: str) -> None:
        store, ref = self._history(session)
        store.git(["cat-file", "-e", f"{sha}^{{commit}}"])
        # Only this conversation's own snapshots: another conversation's
        # commit in the same store is not in this one's list, so restoring it
        # would rewind the files without rewinding the conversation to match.
        if store.run_git(["merge-base", "--is-ancestor", sha, ref]).returncode:
            raise SnapshotError(f"{sha} is not one of this conversation's snapshots")
        body = store.git(["log", "-1", "--format=%B", sha])
        store.restore(sha, keep=_parse_unreadable(body))
        store.git(["update-ref", ref, sha])

    def _copy_history(self, source: str, target: str) -> None:
        head = self._head_sha(source)
        store, ref = self._history(target)
        if head is not None:
            store.git(["update-ref", ref, head])
        elif self._head_sha(target) is not None:
            store.git(["update-ref", "-d", ref])

    def _head_sha(self, session: str) -> str | None:
        store, ref = self._history(session)
        result = store.run_git(["rev-parse", "--verify", "-q", ref])
        return result.stdout.strip() if result.returncode == 0 else None


class _History(NamedTuple):
    store: SnapshotStore
    ref: str


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
