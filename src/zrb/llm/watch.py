"""Watches: work that outlives a turn, and how it reports itself when it ends.

A tool that starts something longer than its own call — a background command, a
delegation, a pipeline — opens a *watch* here and returns. The watch is written
to a per-session ledger under ``CFG.LLM_WATCH_DIR`` *before* the work starts, so
a crash leaves a record of what was about to happen rather than nothing.

The ledger never *infers* how the work ended. Whoever knows says so:

* the process that watched it end writes an ``ended`` row (exit code, or killed);
* a command wrapped by `wrap_to_report` writes its own exit code to a sidecar
  file as it exits, which is what survives a zrb that is already gone.

A watch with neither is simply not known to have ended. It is reported once as
such, and again when its sidecar appears. Nothing here probes a pid, because a
pid says whether *a* process exists, never whether it is the one that was asked.

What the file holds is what was started, how it ended, and where its output is —
never the output itself, because a log tail can carry a token and this file must
stay boring on disk. The live half — the task being awaited, the cancel token,
the loop — belongs to whichever registry owns it and is deliberately not here.

A watch is shown in the next turn's live context and marked delivered as it is
shown, once for "not known to have ended" and once for its final outcome.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape

from zrb.config.config import CFG
from zrb.llm.ambient_state import get_current_chat_session_id
from zrb.util.file_lock import FileLockTimeout, hold_file_lock

RUNNING = "running"
FINISHED = "finished"
KILLED = "killed"
FAILED = "failed"

# Ledger operations, as written on disk. A row is an event, not a state: the
# current state of a watch is the fold of its events, so an append costs one
# line and a crash costs at most the line being written.
OPENED = "opened"
ENDED = "ended"
DELIVERED = "delivered"

# What a delivery told the reader. A watch not known to have ended is shown once
# as that; its final outcome is shown once again, because the first line said the
# answer was still to come.
STAGE_PENDING = "pending"
STAGE_FINAL = "final"

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

# Run by `sh` around the real command: the exit code lands in a file, written
# whole and moved into place, so a reader sees all of it or none. It is the one
# thing that still reports after the zrb that started the command is gone.
_REPORT_EXIT = (
    'f="$1"; shift; "$@"; rc=$?; '
    '{ printf "%s" "$rc" > "$f.tmp" && mv -f "$f.tmp" "$f"; } 2>/dev/null; '
    'exit "$rc"'
)


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


def _ledger_stem(session: str) -> str:
    """The filename stem of *session*.

    Sanitising alone is not injective — `team/a` and `team_a` would share one
    file and each would render the other's watches — so a digest of the exact
    key follows the readable stem.
    """
    digest = hashlib.sha1(session.encode("utf-8"), usedforsecurity=False)
    return f"{_safe_name(session)}-{digest.hexdigest()[:8]}"


def wrap_to_report(argv: list[str], exit_file: str) -> list[str]:
    """Wrap *argv* so the command writes its own exit code to *exit_file*.

    Unchanged where there is no `sh` to do it (Windows) or no file to write: the
    watch then has only the ending its own process can observe, and says so
    instead of claiming more. The wrapper does not `exec` the command, so the pid
    the caller holds is the wrapper's and a kill of its process group still takes
    both.
    """
    if not exit_file or os.name == "nt" or not shutil.which("sh"):
        return argv
    return ["sh", "-c", _REPORT_EXIT, "sh", exit_file, *argv]


# Which run of zrb opened a watch. A `running` row carrying another instance's
# id belongs to a run that is gone: nobody here will write its ending, so it is
# the sidecar or nothing.
_INSTANCE = uuid.uuid4().hex[:8]


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
    # Where the command writes its own exit code, when it was wrapped to.
    exit_file: str = ""
    delivered_at: str = ""
    # What the last delivery told the reader: "", `STAGE_PENDING`, `STAGE_FINAL`.
    delivered_stage: str = ""
    # Which run of zrb opened it.
    instance: str = _INSTANCE

    def is_final(self) -> bool:
        """Whether this watch is known to have ended."""
        return self.state != RUNNING

    def is_orphan(self) -> bool:
        """Whether a run that is gone left this open, with no ending to be seen."""
        return self.state == RUNNING and self.instance != _INSTANCE

    def is_unread(self) -> bool:
        """Whether there is something about this watch the reader has not heard."""
        if self.is_final():
            return self.delivered_stage != STAGE_FINAL
        return self.is_orphan() and not self.delivered_stage


class WatchLedger:
    """The append-only record of one session's watches.

    Every write is one JSON line, and the state of a watch is read back by
    folding those lines. Nothing is rewritten in place except by `compact`,
    which runs when a session opens its ledger.
    """

    def __init__(self, directory: str, session: str) -> None:
        self.directory = directory
        self.session = session
        stem = _ledger_stem(session)
        self.stem = stem
        self.path = os.path.join(directory, f"{stem}.jsonl")
        self._lock = threading.Lock()

    def exit_file_for(self, watch_id: str) -> str:
        """Where a command watched under *watch_id* writes its own exit code."""
        return os.path.join(self.directory, f"{self.stem}.{_safe_name(watch_id)}.exit")

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
                    yield
            except FileLockTimeout as e:
                raise LedgerUnavailable(str(e)) from e

    def _write_row(self, row: dict) -> None:
        """Append one row. Only ever called while `_hold` is held."""
        _write_private(self.path, _encode(row) + "\n", append=True)

    def _close(
        self,
        watch_id: str,
        state: str,
        exit_code: int | None = None,
        outcome: str = "",
    ) -> None:
        with self._hold():
            self._write_row(
                {
                    "op": ENDED,
                    "id": watch_id,
                    "state": state,
                    "exit_code": exit_code,
                    "outcome": outcome,
                    "ended_at": _now(),
                }
            )

    def open(
        self,
        watch_id: str,
        kind: str,
        what: str,
        outcome: str = "",
        recheck: str = "",
        exit_file: str = "",
    ) -> WatchRecord:
        """Record a watch before its work starts; returns the row as stored."""
        record = WatchRecord(
            id=watch_id,
            session=self.session,
            kind=kind,
            what=_shorten(what),
            outcome=outcome,
            recheck=recheck,
            exit_file=exit_file,
        )
        with self._hold():
            self._write_row({"op": OPENED, **asdict(record)})
        return record

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

    def fail(self, watch_id: str) -> None:
        """Record that the work never started, which is not an unknown outcome."""
        self._close(watch_id, FAILED)

    def records(self) -> list[WatchRecord]:
        """Every watch this session has opened, folded to its current state.

        A watch still open whose command wrote its own exit code is settled from
        that file: the command is the one witness that outlives everything else.
        """
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
            elif row.get("op") == ENDED and watch_id in state:
                record = state[watch_id]
                record.state = str(row.get("state", FINISHED))
                record.exit_code = _as_int(row.get("exit_code"))
                record.outcome = str(row.get("outcome", "") or record.outcome)
                record.ended_at = str(row.get("ended_at", ""))
            elif row.get("op") == DELIVERED and watch_id in state:
                state[watch_id].delivered_at = str(row.get("at", ""))
                state[watch_id].delivered_stage = str(
                    row.get("stage", STAGE_FINAL) or STAGE_FINAL
                )
        records = list(state.values())
        for record in records:
            _settle_from_exit_file(record)
        return records

    def unread(self) -> list[WatchRecord]:
        """The watches with something the reader has not heard, oldest first."""
        return [record for record in self.records() if record.is_unread()]

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
                kept: list[WatchRecord] = []
                for record in self.records():
                    if record.state == RUNNING or record.is_unread():
                        kept.append(record)
                    else:
                        _remove(record.exit_file)
                lines = [line for record in kept for line in _fold_lines(record)]
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
        would otherwise both see an unread outcome and both show it.
        """
        hidden_ids = skip or set()
        try:
            with self._hold():
                unread = [
                    record for record in self.unread() if record.id not in hidden_ids
                ]
                shown = unread[:MAX_RENDERED_WATCHES]
                at = _now()
                for record in shown:
                    self._write_row(
                        {
                            "op": DELIVERED,
                            "id": record.id,
                            "at": at,
                            "stage": (
                                STAGE_FINAL if record.is_final() else STAGE_PENDING
                            ),
                        }
                    )
                hidden = len(unread) - len(shown)
        except LedgerUnavailable:
            # Another zrb is writing this ledger; nothing is marked, so the next
            # turn can show these rather than dropping them.
            return []
        lines = [_render(record) for record in shown]
        if hidden:
            lines.append(f"  {hidden} more watch(es) to report; see {self.path}")
        return lines

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
    "state",
    "exit_code",
    "ended_at",
    "outcome",
    "recheck",
    "exit_file",
}
_TEXT_FIELDS = _RECORD_FIELDS - {"exit_code"}


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
        if key == "exit_code":
            fields[key] = _as_int(value)
        elif key in _TEXT_FIELDS and value is not None:
            fields[key] = str(value)
    return fields


def _settle_from_exit_file(record: WatchRecord) -> None:
    """Close an open watch from the exit code its own command left behind."""
    if record.state != RUNNING or not record.exit_file:
        return
    try:
        with open(record.exit_file, encoding="utf-8") as stream:
            code = _as_int(stream.read().strip())
        stamp = os.path.getmtime(record.exit_file)
    except OSError:
        return
    if code is None:
        return
    record.state = FINISHED
    record.exit_code = code
    record.ended_at = (
        datetime.fromtimestamp(stamp, timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds")
    )


def _remove(path: str) -> None:
    """Delete *path* if it is there; a file that will not go costs nothing."""
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass


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

    A kept watch is written as the rows its events fold to: what was opened, how
    it ended if it has, and what the reader has been told. Nothing is lost by
    dropping the rest of its history, because the fold of these rows is the same
    record. A watch settled from its exit file is written with the ending it was
    settled to, so the file is no longer needed to say how it ended.
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
                "exit_file": record.exit_file,
                "instance": record.instance,
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
    if record.delivered_stage:
        lines.append(
            _encode(
                {
                    "op": DELIVERED,
                    "id": record.id,
                    "at": record.delivered_at,
                    "stage": record.delivered_stage,
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
    what = escape(record.what, quote=False)
    watch_id = escape(record.id, quote=False)
    if not record.is_final():
        return (
            f"- Watch {watch_id}: no ending recorded, and the run that started it "
            f"is gone — it may still be running, or may have been stopped with "
            f"that run. This is said once; its exit code will be reported if it "
            f"is ever written: {what}"
        )
    ending = {
        FINISHED: f"exit {record.exit_code}",
        KILLED: f"killed (exit {record.exit_code})",
        FAILED: "never started",
    }.get(record.state, record.state)
    line = f"- Watch {watch_id} {ending}: {what}"
    if record.ended_at:
        line += f" (ended {escape(record.ended_at, quote=False)})"
    if record.outcome:
        line += f"; output at {escape(record.outcome, quote=False)}"
    else:
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
            ledger.compact()
            _LEDGERS[(directory, key)] = ledger
        return ledger


def reset_watch_ledgers() -> None:
    """Forget the cached ledgers, so a test or a new directory starts clean."""
    with _LEDGERS_LOCK:
        _LEDGERS.clear()
