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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape

from zrb.config.config import CFG
from zrb.llm.ambient_state import get_current_chat_session_id

RUNNING = "running"
FINISHED = "finished"
KILLED = "killed"
LOST = "lost"
FAILED = "failed"

# Ledger operations, as written on disk. A row is an event, not a state: the
# current state of a watch is the fold of its events, so an append costs one
# line and a crash costs at most the line being written.
OPENED = "opened"
ENDED = "ended"
DELIVERED = "delivered"

# Sessions kept apart in the prompt: a long-lived session should not crowd the
# live context out with watches nobody will read.
MAX_RENDERED_WATCHES = 5
# How much of a command or purpose the ledger keeps.
MAX_WHAT_CHARS = 120


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
    digest = hashlib.sha1(session.encode("utf-8")).hexdigest()[:8]
    return f"{_safe_name(session)}-{digest}.jsonl"


# Which run of zrb opened a watch. A `running` row carrying another instance's
# id was never closed, because that process is gone: its ending was not seen and
# saying nothing about it would leave it invisible forever.
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
    delivered_at: str = ""
    # Which run of zrb opened it, and the pid that ran the work: the pair is how
    # a row left behind by a dead process is told from one still running here.
    instance: str = _INSTANCE
    pid: int = 0

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
            pid=os.getpid(),
        )
        self._append({"op": OPENED, **asdict(record)})
        return record

    def end(
        self, watch_id: str, exit_code: int | None = None, killed: bool = False
    ) -> None:
        """Record how a watch ended: its exit code, or that it was killed."""
        self._append(
            {
                "op": ENDED,
                "id": watch_id,
                "state": KILLED if killed else FINISHED,
                "exit_code": exit_code,
                "ended_at": _now(),
            }
        )

    def lose(self, watch_id: str) -> None:
        """Record that a watch's ending was never seen — not that it is running."""
        self._append(
            {
                "op": ENDED,
                "id": watch_id,
                "state": LOST,
                "ended_at": _now(),
            }
        )

    def fail(self, watch_id: str) -> None:
        """Record that the work never started, which is not an unknown outcome."""
        self._append(
            {
                "op": ENDED,
                "id": watch_id,
                "state": FAILED,
                "ended_at": _now(),
            }
        )

    def mark_delivered(self, watch_ids: list[str]) -> None:
        """Say that these outcomes have been shown, once and for all."""
        at = _now()
        for watch_id in watch_ids:
            self._append({"op": DELIVERED, "id": watch_id, "at": at})

    def records(self) -> list[WatchRecord]:
        """Every watch this session has opened, folded to its current state."""
        state: dict[str, WatchRecord] = {}
        for row in self._read_rows():
            watch_id = str(row.get("id", ""))
            if not watch_id:
                continue
            if row.get("op") == OPENED:
                fields = {k: v for k, v in row.items() if k in _RECORD_FIELDS}
                # A shared or hand-edited file must not lend one session
                # another's watches: the row says whose it is, so check.
                if fields.get("session", self.session) != self.session:
                    continue
                state[watch_id] = WatchRecord(**fields)  # type: ignore[arg-type]
            elif row.get("op") == ENDED and watch_id in state:
                record = state[watch_id]
                record.state = str(row.get("state", FINISHED))
                record.exit_code = row.get("exit_code")
                record.ended_at = str(row.get("ended_at", ""))
            elif row.get("op") == DELIVERED and watch_id in state:
                state[watch_id].delivered_at = str(row.get("at", ""))
        return list(state.values())

    def unread(self) -> list[WatchRecord]:
        """The watches whose outcome has not been shown yet, oldest first."""
        return [record for record in self.records() if record.is_unread()]

    def reconcile(self) -> list[str]:
        """Report a previous run's unfinished watches as lost, and return their ids.

        A row still `running` under another instance's id was never closed: that
        process died, or was killed without the exit path running. Leaving it as
        "running" would make it invisible forever — worse than saying the ending
        was not seen.
        """
        lost: list[str] = []
        for record in self.records():
            if record.state != RUNNING or record.instance == _INSTANCE:
                continue
            self.lose(record.id)
            lost.append(record.id)
        return lost

    def compact(self) -> None:
        """Rewrite the file with only the watches that still say something.

        A session that opens its ledger does this once, so a year of finished
        and delivered watches cannot become a megabyte read on every turn.
        """
        keep = [
            record
            for record in self.records()
            if record.state == RUNNING or record.is_unread()
        ]
        lines: list[str] = []
        for record in keep:
            lines.append(
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
                        "state": RUNNING,
                        "exit_code": None,
                        "ended_at": "",
                    }
                )
            )
            if record.state != RUNNING:
                lines.append(
                    _encode(
                        {
                            "op": ENDED,
                            "id": record.id,
                            "state": record.state,
                            "exit_code": record.exit_code,
                            "ended_at": record.ended_at,
                        }
                    )
                )
        with self._lock:
            os.makedirs(self.directory, exist_ok=True)
            temporary = f"{self.path}.tmp"
            _write_private(temporary, "".join(line + "\n" for line in lines))
            os.replace(temporary, self.path)

    def render_lines(self, skip: "set[str] | None" = None) -> list[str]:
        """The live-context lines for this session's unread watches.

        *skip* names the watches the caller already reports in full — a handle
        the live registry still holds — so the block says each fact once.
        Rendering is delivery: an outcome is shown once and then marked, so a
        quiet session costs no prompt at all.
        """
        hidden_ids = skip or set()
        unread = [record for record in self.unread() if record.id not in hidden_ids]
        if not unread:
            return []
        shown = unread[:MAX_RENDERED_WATCHES]
        lines = [_render(record) for record in shown]
        hidden = len(unread) - len(shown)
        if hidden:
            lines.append(f"  {hidden} more watch(es) finished; see {self.path}")
        self.mark_delivered([record.id for record in shown])
        return lines

    def _append(self, row: dict) -> None:
        with self._lock:
            os.makedirs(self.directory, exist_ok=True)
            _write_private(self.path, _encode(row) + "\n", append=True)

    def _read_rows(self) -> list[dict]:
        try:
            with open(self.path, encoding="utf-8") as stream:
                lines = stream.readlines()
        except OSError:
            return []
        rows: list[dict] = []
        for line in lines:
            try:
                rows.append(json.loads(line))
            except ValueError:
                # A torn last line from a crash costs that one row, not the file.
                continue
        return rows


_RECORD_FIELDS = {
    "id",
    "session",
    "kind",
    "what",
    "opened_at",
    "instance",
    "pid",
    "state",
    "exit_code",
    "ended_at",
    "outcome",
    "recheck",
}


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


def _render(record: WatchRecord) -> str:
    """One watch as the live context shows it: the outcome, not a reminder.

    Every field here can be a command line or a caller's free text, so it is
    escaped: a description must not be able to close the `<live-context>` block
    or open one of its own.
    """
    ending = {
        FINISHED: f"exit {record.exit_code}",
        KILLED: f"killed (exit {record.exit_code})",
        LOST: "outcome unknown",
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
