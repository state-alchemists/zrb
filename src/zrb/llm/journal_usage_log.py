"""A local, append-only record of how the journal is used.

Sits beside the usage log (`zrb.llm.usage_log`): the same directory, the same
one-file-per-month layout and the same read tolerance, in `journal-YYYY-MM.jsonl`.
It exists so `/usage` can say what the journal costs and whether it pays: how
many bytes the index adds to a turn, how often a search finds nothing, and
whether a note the agent wrote is ever read again.

One line per event: `injected`, `prompted`, `searched`, `auto_searched`, `read`,
`written`, `superseded`, `deleted`, `judging`, `judged`. Like the usage log it
holds numbers and ids only.
A note is identified by a short hash of its `category/slug`, never by the name,
because a slug carries meaning; `/usage` resolves a hash to a title by scanning
the current journal, so a note that no longer exists reads as removed. No query,
no note text, no title and no HUD line is ever written.

The judge pair exists because a compliance run is fire-and-forget: `judging`
says one was dispatched and `judged` says it came back, so a run that never
finished is visible as a start with no end — the state a silent miss hid in.

Recording never raises: a journal tool must not fail because a log could not be
written.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from zrb.config.config import CFG
from zrb.llm.ambient_state import get_current_context_session
from zrb.llm.usage_log import as_datetime, store_files, store_path
from zrb.util.string.name import get_conversation_key

_FILE_PREFIX = "journal-"
_HASH_LENGTH = 10
_ACTIVITY_DIR = "activity-log"
_INDEX_NAME = "index.md"

INJECTED = "injected"
PROMPTED = "prompted"
SEARCHED = "searched"
AUTO_SEARCHED = "auto_searched"
READ = "read"
WRITTEN = "written"
SUPERSEDED = "superseded"
DELETED = "deleted"
JUDGING = "judging"
JUDGED = "judged"
EVENTS = (
    INJECTED,
    PROMPTED,
    SEARCHED,
    AUTO_SEARCHED,
    READ,
    WRITTEN,
    SUPERSEDED,
    DELETED,
    JUDGING,
    JUDGED,
)


@dataclass(frozen=True)
class JournalEvent:
    """One journal event, as it is written to the log."""

    timestamp: datetime
    session: str
    event: str
    # injected: bytes added to the turn, whether the cap cut the index, and the
    # hashed ids of the notes whose HUD line made it in.
    size: int = 0
    truncated: bool = False
    hud: list[str] = field(default_factory=list)
    # searched: how many words, how many result rows, and the hashed ids of the
    # notes those rows came from.
    terms: int = 0
    results: int = 0
    hits: list[str] = field(default_factory=list)
    # read / written / superseded / deleted: the hashed id of the note.
    note: str = ""
    # judging / judged: how many tool calls the run made, and whether it failed.
    tool_calls: int = 0
    failed: bool = False

    @property
    def is_zero_result(self) -> bool:
        return self.event == SEARCHED and self.results == 0

    def to_dict(self) -> dict[str, object]:
        raw = dataclasses.asdict(self)
        raw["timestamp"] = self.timestamp.isoformat()
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> JournalEvent:
        """Rebuild an event; raises when *raw* is not one."""
        event = str(raw["event"])
        if event not in EVENTS:
            raise ValueError(f"unknown journal event: {event!r}")
        return cls(
            timestamp=as_datetime(raw["timestamp"]),
            session=str(raw.get("session", "")),
            event=event,
            size=_as_int(raw.get("size")),
            truncated=raw.get("truncated") is True,
            hud=_as_ids(raw.get("hud")),
            terms=_as_int(raw.get("terms")),
            results=_as_int(raw.get("results")),
            hits=_as_ids(raw.get("hits")),
            note=str(raw.get("note") or ""),
            tool_calls=_as_int(raw.get("tool_calls")),
            failed=raw.get("failed") is True,
        )


def note_hash(note_id: str) -> str:
    """The short stable hash that stands for `category/slug` in the log."""
    return hashlib.sha256(note_id.encode("utf-8")).hexdigest()[:_HASH_LENGTH]


def note_id_of(rel: str) -> str | None:
    """`category/slug` for a journal-relative note path, else ``None``.

    Indexes and the activity log are not notes: a path is one only when it is
    `<category>/<slug>.md` and the file is not an index."""
    parts = rel.replace(os.sep, "/").split("/")
    if len(parts) != 2 or parts[0] == _ACTIVITY_DIR or not parts[1].endswith(".md"):
        return None
    if parts[1] in (_INDEX_NAME, CFG.LLM_JOURNAL_INDEX_FILE):
        return None
    return f"{parts[0]}/{parts[1].removesuffix('.md')}"


def record_injected(size: int, hud_notes: list[str], truncated: bool) -> None:
    """The index was injected: *size* bytes, carrying *hud_notes* (rel paths)."""
    hud = [note_hash(nid) for nid in map(note_id_of, hud_notes) if nid]
    _append(INJECTED, size=size, truncated=truncated, hud=hud)


def record_prompted() -> None:
    """A user prompt started a turn: the denominator of lookups per answer.

    One per submitted prompt, not per model round. A turn that makes six tool
    calls is still one question, and counting rounds would make an agent that
    searches once look cheaper than one that searches once and reads twice."""
    _append(PROMPTED)


def record_searched(query: str, result_files: list[str], results: int) -> None:
    """A search ran: *result_files* are the rel paths its rows came from."""
    _append_search(SEARCHED, query, result_files, results)


def record_auto_searched(query: str, result_files: list[str], results: int) -> None:
    """The opening-message auto-search ran, so its yield is visible.

    Kept apart from `searched`: that event counts a search the agent chose to
    make, and folding in one it never asked for would make an automatic miss
    read as the agent's own — the reason `find_in_journal` records nothing."""
    _append_search(AUTO_SEARCHED, query, result_files, results)


def _append_search(
    event: str, query: str, result_files: list[str], results: int
) -> None:
    ids = {nid for nid in map(note_id_of, result_files) if nid}
    _append(
        event,
        terms=len(query.split()),
        results=results,
        hits=sorted(note_hash(nid) for nid in ids),
    )


def record_note_event(event: str, category: str, slug: str) -> None:
    """A write, supersede or delete of the note `category/slug`."""
    _append(event, note=note_hash(f"{category}/{slug}"))


def record_judging() -> None:
    """The compliance judge was dispatched for this turn."""
    _append(JUDGING)


def record_judged(tool_calls: int, failed: bool) -> None:
    """The judge came back: *tool_calls* journal calls it made, or *failed*."""
    _append(JUDGED, tool_calls=tool_calls, failed=failed)


def record_path_read(abs_path: str) -> None:
    """A file was read; recorded only when it is a note under the journal."""
    rel = _journal_relative(abs_path)
    nid = note_id_of(rel) if rel else None
    if nid:
        _append(READ, note=note_hash(nid))


def read_events(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    session_key: str | None = None,
    directory: str | None = None,
) -> list[JournalEvent]:
    """Every event in the window, oldest first; an unreadable line is skipped."""
    events: list[JournalEvent] = []
    for path in store_files(_FILE_PREFIX, since, until, directory):
        events.extend(_read_file(path, since, until, session_key))
    events.sort(key=lambda event: event.timestamp)
    return events


def _journal_relative(abs_path: str) -> str:
    root = CFG.LLM_JOURNAL_DIR
    if not root:
        return ""
    base = os.path.realpath(os.path.expanduser(root))
    target = os.path.realpath(abs_path)
    try:
        if os.path.commonpath([base, target]) != base:
            return ""
    except ValueError:  # another drive on Windows
        return ""
    return os.path.relpath(target, base)


def _append(
    event: str,
    *,
    size: int = 0,
    truncated: bool = False,
    hud: list[str] | None = None,
    terms: int = 0,
    results: int = 0,
    hits: list[str] | None = None,
    note: str = "",
    tool_calls: int = 0,
    failed: bool = False,
) -> None:
    """Write one line; a failure is logged at debug and swallowed."""
    try:
        now = datetime.now(timezone.utc)
        session = get_conversation_key(get_current_context_session())
        line = JournalEvent(
            timestamp=now,
            session=session,
            event=event,
            size=size,
            truncated=truncated,
            hud=hud or [],
            terms=terms,
            results=results,
            hits=hits or [],
            note=note,
            tool_calls=tool_calls,
            failed=failed,
        )
        path = store_path(_FILE_PREFIX, now)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(line.to_dict(), ensure_ascii=False) + "\n")
    except (OSError, ValueError):
        CFG.LOGGER.debug("Journal usage log not written", exc_info=True)


def _read_file(
    path: str,
    since: datetime | None,
    until: datetime | None,
    session_key: str | None,
) -> list[JournalEvent]:
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []
    events: list[JournalEvent] = []
    for line in lines:
        event = _parse_line(line)
        if event is None:
            continue
        if since is not None and event.timestamp < as_datetime(since):
            continue
        if until is not None and event.timestamp > as_datetime(until):
            continue
        if session_key is not None and event.session != session_key:
            continue
        events.append(event)
    return events


def _parse_line(line: str) -> JournalEvent | None:
    text = line.strip()
    if not text:
        return None
    try:
        return JournalEvent.from_dict(json.loads(text))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        CFG.LOGGER.debug(f"Skipping an unreadable journal event: {text[:80]}")
        return None


def _as_int(value: object) -> int:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return 0


def _as_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
