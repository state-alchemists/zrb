"""Watches: work that outlives a turn, and how it reports itself when it ends.

A tool that starts something longer than its own call — a background command, a
delegation, a pipeline — opens a *watch* here and returns. The watch is written
to a per-session ledger under ``CFG.LLM_WATCH_DIR`` *before* the work starts, so
a crash leaves a record of what was about to happen rather than nothing, and the
process that ends the work closes the watch with its outcome.

This is the half of a watch that survives the process: what was started, how it
ended, and where its output is — never the output itself, because a log tail can
carry a token and this file must stay boring on disk. The live half — the task
being awaited, the cancel token, the loop — belongs to whichever registry owns
it and is deliberately not stored here.

A finished watch is shown once, in the next turn's live context, and marked
delivered as it is shown. That is the whole point: a result that arrives while
nobody is looking stops being something a model has to remember to fetch.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape

import psutil

from zrb.config.config import CFG
from zrb.llm.ambient_state import get_current_chat_session_id
from zrb.util.file_lock import FileLockTimeout, hold_file_lock

RUNNING = "running"
FINISHED = "finished"
KILLED = "killed"
LOST = "lost"
FAILED = "failed"

# Ledger operations, as written on disk. A row is an event, not a state: the
# current state of a watch is the fold of its events, so an append costs one
# line and a crash costs at most the line being written.
OPENED = "opened"
SPAWNED = "spawned"
ENDED = "ended"
DELIVERED = "delivered"

# Sessions kept apart in the prompt: a long-lived session should not crowd the
# live context out with watches nobody will read.
MAX_RENDERED_WATCHES = 5
# How long a write waits for another zrb process working on the same session's
# file. A ledger that cannot be written costs the record, never the work it was
# recording, so this is short enough to give up and long enough to outlast the
# one thing that holds it: another process folding the same file.
LEDGER_LOCK_TIMEOUT = 5.0
# How much of a command or purpose the ledger keeps.
MAX_WHAT_CHARS = 120


class LedgerUnavailable(OSError):
    """This ledger could not be written just now: another zrb holds it, or the
    disk refused. It is an `OSError` because that is what every caller already
    treats as "the record is lost, not the work"."""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _shorten(text: str) -> str:
    collapsed = " ".join(str(text).split())
    if len(collapsed) <= MAX_WHAT_CHARS:
        return collapsed
    return collapsed[: MAX_WHAT_CHARS - 1] + "…"


def _safe_name(session: str) -> str:
    """A session key as a filename stem: readable, but not the whole answer."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session).strip("._") or "_"


def _ledger_filename(session: str) -> str:
    """The file of *session*.

    Sanitising alone is not injective — `team/a` and `team_a` would share one
    file and each would render the other's watches — so a digest of the exact
    key follows the readable stem.
    """
    digest = hashlib.sha1(session.encode("utf-8"), usedforsecurity=False).hexdigest()[
        :8
    ]
    return f"{_safe_name(session)}-{digest}.jsonl"


# Which run of zrb opened a watch. A `running` row carrying another instance's
# id was never closed, because that process is gone: its ending was not seen and
# saying nothing about it would leave it invisible forever.
_INSTANCE = uuid.uuid4().hex[:8]


def _process_start(pid: int) -> float:
    """When process *pid* began, as the OS reports it; 0.0 when it cannot say.

    A pid alone does not name a process: once the child is gone the OS may hand
    the number to something unrelated. The pair (pid, start time) does.
    """
    try:
        return float(psutil.Process(pid).create_time())
    except (psutil.Error, OSError, ValueError):
        return 0.0


def _is_alive(pid: int, start: float = 0.0) -> bool:
    """Whether the process that was *pid* — started at *start* — still exists.

    With a recorded start time, a live process that began at another time is a
    stranger that inherited the pid, not the child. Without one (an older row, or
    a platform that would not say) existence has to do.

    Existence alone is asked with signal 0, which reports it without touching the
    process.

    Asked with signal 0, which reports existence without touching the process.
    On Windows `os.kill` is `TerminateProcess`, so asking would end the work this
    question is about — there the answer is "assume alive", which keeps the watch
    open rather than declaring a running command lost.
    """
    if pid <= 0:
        return False
    if start > 0:
        found = _process_start(pid)
        if found > 0:
            # create_time is a float of the kernel's own clock; a second of slack
            # absorbs rounding between two readings of the same process.
            return abs(found - start) < 1.0
        if not psutil.pid_exists(pid):
            return False
    if os.name != "posix":
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # It exists; it just belongs to someone else.
        return True
    except OSError:
        return False
    return True


@dataclass
class WatchRecord:
    """One watch, as the ledger holds it."""

    id: str
    session: str
    kind: str
    what: str
    opened_at: str = field(default_factory=_now)
    state: str = RUNNING
    exit_code: int | None = None
    ended_at: str = ""
    outcome: str = ""
    recheck: str = ""
    delivered_at: str = ""
    # Which run of zrb opened it, and the pid that ran the work: the pair is how
    # a row left behind by a dead process is told from one still running here.
    instance: str = _INSTANCE
    pid: int = 0
    pid_start: float = 0.0

    def is_unread(self) -> bool:
        """Whether this watch has an outcome nobody has been told yet."""
        return self.state in (FINISHED, KILLED, LOST, FAILED) and not self.delivered_at


class WatchLedger:
    """The append-only record of one session's watches.

    Every write is one JSON line, and the state of a watch is read back by
    folding those lines. Nothing is rewritten in place except by `compact`,
    which runs when a session opens its ledger.
    """

    def __init__(self, directory: str, session: str) -> None:
        self.directory = directory
        self.session = session
        self.path = os.path.join(directory, _ledger_filename(session))
        self._lock = threading.Lock()
        # Endings that could not be written when they happened. The process they
        # describe is gone and no other path will report it, so they are kept
        # here and written the next time the lock is ours.
        self._pending: list[tuple[str, str, int | None, str, str]] = []

    @contextmanager
    def _hold(self) -> Iterator[None]:
        """Hold the lock that makes a read-modify-write of this file one step.

        Two zrb processes can share one session's ledger, so every write takes
        the file lock. An append is a single small write and would survive on its
        own; a compaction rewrites the whole file from what it read, and a row
        appended between that read and the replace would be gone. So the fold
        reads inside the lock, and appends take the same lock, because the point
        of the lock is that nobody writes outside it.
        """
        with self._lock:
            os.makedirs(self.directory, exist_ok=True)
            try:
                with hold_file_lock(f"{self.path}.lock", timeout=LEDGER_LOCK_TIMEOUT):
                    self._flush_pending()
                    yield
            except FileLockTimeout as e:
                raise LedgerUnavailable(str(e)) from e

    def _write_row(self, row: dict) -> None:
        """Append one row. Only ever called while `_hold` is held."""
        _write_private(self.path, _encode(row) + "\n", append=True)

    def _flush_pending(self) -> None:
        """Write the endings that missed their turn. Only while the lock is held.

        A ledger that stays unwritable keeps them for the next try; the work they
        describe has ended either way, so they are never dropped.
        """
        while self._pending:
            watch_id, state, exit_code, outcome, ended_at = self._pending[0]
            try:
                self._write_end(watch_id, state, exit_code, outcome, ended_at)
            except OSError:
                return
            self._pending.pop(0)

    def _close(
        self,
        watch_id: str,
        state: str,
        exit_code: int | None = None,
        outcome: str = "",
    ) -> None:
        """Close a watch, or keep the ending to write later if it cannot be.

        The ending is stamped now, not when it is finally written, so a retry does
        not move it. The failure is still raised: the caller logs it, but the
        record is no longer lost with it.
        """
        ended_at = _now()
        try:
            with self._hold():
                self._write_end(watch_id, state, exit_code, outcome, ended_at)
        except OSError:
            self._pending.append((watch_id, state, exit_code, outcome, ended_at))
            raise

    def _write_end(
        self,
        watch_id: str,
        state: str,
        exit_code: int | None = None,
        outcome: str = "",
        ended_at: str = "",
    ) -> None:
        """Write the one row that closes a watch. Only while `_hold` is held."""
        self._write_row(
            {
                "op": ENDED,
                "id": watch_id,
                "state": state,
                "exit_code": exit_code,
                "outcome": outcome,
                "ended_at": ended_at or _now(),
            }
        )

    def open(
        self,
        watch_id: str,
        kind: str,
        what: str,
        outcome: str = "",
        recheck: str = "",
    ) -> WatchRecord:
        """Record a watch before its work starts; returns the row as stored."""
        record = WatchRecord(
            id=watch_id,
            session=self.session,
            kind=kind,
            what=_shorten(what),
            outcome=outcome,
            recheck=recheck,
        )
        self._append({"op": OPENED, **asdict(record)})
        return record

    def started(self, watch_id: str, pid: int) -> None:
        """Record the pid that runs the work, once the process exists.

        `opened` is written before the spawn, so it cannot know the pid; this is
        the row that lets a later run tell "the work is still going" from "the
        run that started it is gone".
        """
        self._append(
            {
                "op": SPAWNED,
                "id": watch_id,
                "pid": pid,
                "pid_start": _process_start(pid),
            }
        )

    def end(
        self,
        watch_id: str,
        exit_code: int | None = None,
        killed: bool = False,
        outcome: str = "",
    ) -> None:
        """Record how a watch ended: its exit code, or that it was killed.

        *outcome* is where the full output still is, when the watch has somewhere
        to point: the next turn may read it, but the ledger keeps the pointer and
        never the output.
        """
        self._close(watch_id, KILLED if killed else FINISHED, exit_code, outcome)

    def lose(self, watch_id: str) -> None:
        """Record that a watch's ending was never seen — not that it is running."""
        self._close(watch_id, LOST)

    def fail(self, watch_id: str) -> None:
        """Record that the work never started, which is not an unknown outcome."""
        self._close(watch_id, FAILED)

    def mark_delivered(self, watch_ids: list[str]) -> None:
        """Say that these outcomes have been shown, once and for all."""
        with self._hold():
            self._mark_delivered(watch_ids)

    def _mark_delivered(self, watch_ids: list[str]) -> None:
        """Mark rows delivered. Only while `_hold` is held."""
        at = _now()
        for watch_id in watch_ids:
            self._write_row({"op": DELIVERED, "id": watch_id, "at": at})

    def records(self) -> list[WatchRecord]:
        """Every watch this session has opened, folded to its current state."""
        state: dict[str, WatchRecord] = {}
        for row in self._read_rows():
            watch_id = str(row.get("id", ""))
            if not watch_id:
                continue
            if row.get("op") == OPENED:
                fields = _clean_fields(row)
                # A shared or hand-edited file must not lend one session
                # another's watches: the row says whose it is, so check.
                if fields.get("session", self.session) != self.session:
                    continue
                fields.setdefault("session", self.session)
                fields.setdefault("kind", "")
                fields.setdefault("what", "")
                fields["id"] = watch_id
                state[watch_id] = WatchRecord(**fields)  # type: ignore[arg-type]
            elif row.get("op") == SPAWNED and watch_id in state:
                state[watch_id].pid = _as_int(row.get("pid")) or 0
                state[watch_id].pid_start = _as_float(row.get("pid_start"))
            elif row.get("op") == ENDED and watch_id in state:
                record = state[watch_id]
                record.state = str(row.get("state", FINISHED))
                record.exit_code = _as_int(row.get("exit_code"))
                record.outcome = str(row.get("outcome", "") or record.outcome)
                record.ended_at = str(row.get("ended_at", ""))
            elif row.get("op") == DELIVERED and watch_id in state:
                state[watch_id].delivered_at = str(row.get("at", ""))
        return list(state.values())

    def unread(self) -> list[WatchRecord]:
        """The watches whose outcome has not been shown yet, oldest first."""
        return [record for record in self.records() if record.is_unread()]

    def reconcile(self) -> list[str]:
        """Report a previous run's unfinished watches as lost, and return their ids.

        A row still `running` under another instance's id was left open by a run
        of zrb that is gone. That alone does not mean the work ended: the child
        process may still be running, which is exactly the case where calling it
        lost would be a lie. The recorded pid decides — lost only when that
        process is confirmed absent. `render_lines` asks again every turn, because
        the child that was still alive when this ledger was opened can die later,
        and no process is left to write the ending when it does.
        """
        with self._hold():
            return self._reconcile()

    def _reconcile(self) -> list[str]:
        """The body of `reconcile`, for a caller already holding the lock."""
        lost: list[str] = []
        for record in self.records():
            if record.state != RUNNING or record.instance == _INSTANCE:
                continue
            if _is_alive(record.pid, record.pid_start):
                continue
            self._write_end(record.id, LOST)
            lost.append(record.id)
        return lost

    def compact(self) -> None:
        """Rewrite the file with only the watches that still say something.

        A session that opens its ledger does this once, so a year of finished
        and delivered watches cannot become a megabyte read on every turn. The
        rows are read *inside* the lock that guards the rewrite: reading first
        and locking later would fold a file that has already moved on, and every
        row appended in between would be silently rewritten away.
        """
        try:
            with self._hold():
                lines = [
                    line
                    for record in self.records()
                    if record.state == RUNNING or record.is_unread()
                    for line in _fold_lines(record)
                ]
                temporary = f"{self.path}.tmp"
                _write_private(temporary, "".join(line + "\n" for line in lines))
                os.replace(temporary, self.path)
        except LedgerUnavailable:
            # Another process is folding the same file; its result serves.
            return

    def render_lines(self, skip: "set[str] | None" = None) -> list[str]:
        """The live-context lines for this session's unread watches.

        *skip* names the watches the caller already reports in full — a handle
        the live registry still holds — so the block says each fact once.
        Rendering is delivery: an outcome is shown once and then marked, so a
        quiet session costs no prompt at all. Choosing the rows and marking them
        happen under one lock, because two turns rendering at the same moment
        would otherwise both see an unread outcome and both show it. Reconciliation
        runs first, in the same lock: a watch whose child was still alive when the
        ledger opened, and died since, would otherwise stay `running` for as long
        as this process lives — a result nobody is told about.
        """
        hidden_ids = skip or set()
        try:
            with self._hold():
                self._reconcile()
                unread = [
                    record for record in self.unread() if record.id not in hidden_ids
                ]
                shown = unread[:MAX_RENDERED_WATCHES]
                self._mark_delivered([record.id for record in shown])
                hidden = len(unread) - len(shown)
        except LedgerUnavailable:
            # Another zrb is writing this ledger; nothing is marked, so the next
            # turn can show these rather than dropping them.
            return []
        lines = [_render(record) for record in shown]
        if hidden:
            lines.append(f"  {hidden} more watch(es) finished; see {self.path}")
        return lines

    def _append(self, row: dict) -> None:
        with self._hold():
            self._write_row(row)

    def _read_rows(self) -> list[dict]:
        try:
            with open(self.path, encoding="utf-8") as stream:
                lines = stream.readlines()
        except OSError:
            return []
        rows: list[dict] = []
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                # A torn last line from a crash costs that one row, not the file.
                continue
            # Valid JSON that is not a row (a hand edit, a stray number) is the
            # same loss: one line, never the turn that was reading it.
            if isinstance(row, dict):
                rows.append(row)
        return rows


_RECORD_FIELDS = {
    "id",
    "session",
    "kind",
    "what",
    "opened_at",
    "instance",
    "pid",
    "pid_start",
    "state",
    "exit_code",
    "ended_at",
    "outcome",
    "recheck",
}


_TEXT_FIELDS = _RECORD_FIELDS - {"pid", "pid_start", "exit_code"}


def _as_float(value: object) -> float:
    """*value* as a float, or 0.0 when it is not a number (including a bool)."""
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: object) -> int | None:
    """*value* as an int, or None when it is not one (including a bool)."""
    if isinstance(value, bool):
        return None
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


def _clean_fields(row: dict) -> dict:
    """The record fields of an `opened` row, each of the type the code expects.

    The ledger is a file a person can edit, so a field of the wrong type must
    cost that value, not the render that escapes and formats it.
    """
    fields: dict = {}
    for key, value in row.items():
        if key not in _RECORD_FIELDS:
            continue
        if key == "pid":
            fields[key] = _as_int(value) or 0
        elif key == "pid_start":
            fields[key] = _as_float(value)
        elif key == "exit_code":
            fields[key] = _as_int(value)
        elif key in _TEXT_FIELDS and value is not None:
            fields[key] = str(value)
    return fields


def _encode(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def _write_private(path: str, content: str, append: bool = False) -> None:
    """Write *content*, keeping the file readable only by its owner.

    The mode is applied on every write, not only on create: a ledger restored
    with different permissions, or created by another tool, must not be appended
    to while it is still world-readable.
    """
    flags = os.O_APPEND if append else os.O_TRUNC
    descriptor = os.open(path, os.O_CREAT | os.O_WRONLY | flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
    except (AttributeError, OSError):
        # Windows has no POSIX bits; the mode passed at create still applies.
        pass
    with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
        stream.write(content)


def _fold_lines(record: WatchRecord) -> list[str]:
    """The rows that keep *record* as it stands, after a compaction.

    A kept watch is written as the pair its two events fold to: what was opened,
    and — for one that has ended — how. Nothing is lost by dropping the rest of
    its history, because the fold of these two rows is the same record.
    """
    lines = [
        _encode(
            {
                "op": OPENED,
                "id": record.id,
                "session": record.session,
                "kind": record.kind,
                "what": record.what,
                "opened_at": record.opened_at,
                "outcome": record.outcome,
                "recheck": record.recheck,
                "instance": record.instance,
                "pid": record.pid,
                "pid_start": record.pid_start,
                "state": RUNNING,
                "exit_code": None,
                "ended_at": "",
            }
        )
    ]
    if record.state != RUNNING:
        lines.append(
            _encode(
                {
                    "op": ENDED,
                    "id": record.id,
                    "state": record.state,
                    "exit_code": record.exit_code,
                    "outcome": record.outcome,
                    "ended_at": record.ended_at,
                }
            )
        )
    return lines


def _render(record: WatchRecord) -> str:
    """One watch as the live context shows it: the outcome, not a reminder.

    Every field here can be a command line or a caller's free text, so it is
    escaped: a description must not be able to close the `<live-context>` block
    or open one of its own.
    """
    ending = {
        FINISHED: f"exit {record.exit_code}",
        KILLED: f"killed (exit {record.exit_code})",
        LOST: (
            "outcome unknown"
            if record.pid > 0
            # No pid was ever recorded: the run that opened this watch ended
            # between spawning the command and noting it, so the command may
            # well still be running and nothing here can say.
            else "outcome unknown, and it may still be running"
        ),
        FAILED: "never started",
    }.get(record.state, record.state)
    line = f"- Watch {escape(record.id, quote=False)} {ending}: {escape(record.what, quote=False)}"
    if record.ended_at:
        line += f" (ended {escape(record.ended_at, quote=False)})"
    if record.outcome:
        line += f"; output at {escape(record.outcome, quote=False)}"
    elif record.state != RUNNING:
        line += "; its output is no longer held by this session"
    return line


_LEDGERS: dict[tuple[str, str], WatchLedger] = {}
_LEDGERS_LOCK = threading.Lock()


def get_watch_ledger(session: str | None = None) -> WatchLedger:
    """The ledger of *session* (default: the chat session this call is in)."""
    key = session if session is not None else get_current_chat_session_id()
    key = key or "_"
    directory = CFG.LLM_WATCH_DIR
    with _LEDGERS_LOCK:
        ledger = _LEDGERS.get((directory, key))
        if ledger is None:
            ledger = WatchLedger(directory, key)
            ledger.reconcile()
            ledger.compact()
            _LEDGERS[(directory, key)] = ledger
        return ledger


def reset_watch_ledgers() -> None:
    """Forget the cached ledgers, so a test or a new directory starts clean."""
    with _LEDGERS_LOCK:
        _LEDGERS.clear()
