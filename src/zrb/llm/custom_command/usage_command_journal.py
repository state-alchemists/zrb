"""The `/usage` Journal section: what the journal costs and whether it pays."""

from __future__ import annotations

import os

from zrb.config.config import CFG
from zrb.llm.journal_usage_log import (
    DELETED,
    INJECTED,
    JUDGED,
    JUDGING,
    READ,
    SEARCHED,
    SUPERSEDED,
    WRITTEN,
    JournalEvent,
    note_hash,
)

_NEVER_READ_SHOWN = 5
_TITLE_WIDTH = 48
_REMOVED = "(removed)"


def render_journal_section(
    events: list[JournalEvent], titles: dict[str, str] | None = None
) -> list[str]:
    """The lines of the Journal section; empty when the window has no events.

    *titles* maps a note hash to its title in the current journal; a hash it
    lacks is a note that no longer exists. Left out, it is read from the
    journal on disk."""
    if not events:
        return []
    lines = ["  Journal"]
    for part in (
        _index_line(events),
        _search_line(events),
        _notes_line(events),
        _judge_line(events),
        _never_read_line(events, titles),
    ):
        if part:
            lines.append(f"    {part}")
    return lines if len(lines) > 1 else []


def get_note_titles() -> dict[str, str]:
    """Hash -> title for every note in the current journal."""
    # lazy: zrb internal (heavy via transitive — zrb.llm.tool's __init__
    # imports pydantic_ai-dependent modules)
    from zrb.llm.tool.journal_note import list_notes

    root = os.path.abspath(os.path.expanduser(CFG.LLM_JOURNAL_DIR or ""))
    notes = list_notes(root, (CFG.LLM_JOURNAL_INDEX_FILE, "index.md"))
    return {note_hash(f"{note.category}/{note.slug}"): note.title for note in notes}


def _index_line(events: list[JournalEvent]) -> str:
    injected = [event for event in events if event.event == INJECTED]
    if not injected:
        return ""
    average = sum(event.size for event in injected) // len(injected)
    cut = sum(1 for event in injected if event.truncated)
    return (
        f"index    {_bytes(average)} per injection on average over "
        f"{len(injected)} injection(s) · {cut / len(injected):.0%} truncated"
    )


def _search_line(events: list[JournalEvent]) -> str:
    searches = [event for event in events if event.event == SEARCHED]
    if not searches:
        return ""
    empty = sum(1 for event in searches if event.is_zero_result)
    return (
        f"search   {len(searches)} search(es) · {empty / len(searches):.0%} found "
        f"nothing · {_reworded(events)} reworded straight away"
    )


def _reworded(events: list[JournalEvent]) -> int:
    """Searches whose very next journal event in the same session is a search."""
    by_session: dict[str, list[JournalEvent]] = {}
    for event in events:
        by_session.setdefault(event.session, []).append(event)
    return sum(
        1
        for sequence in by_session.values()
        for first, second in zip(sequence, sequence[1:])
        if first.event == SEARCHED and second.event == SEARCHED
    )


def _notes_line(events: list[JournalEvent]) -> str:
    first_written: dict[str, JournalEvent] = {}
    for event in events:
        if event.event == WRITTEN:
            first_written.setdefault(event.note, event)
    retired = [
        f"{count} {kind}"
        for kind in (SUPERSEDED, DELETED)
        if (count := sum(1 for event in events if event.event == kind))
    ]
    if not first_written and not retired:
        return ""
    reread = sum(
        1 for written in first_written.values() if _is_read_after(events, written)
    )
    line = f"notes    {len(first_written)} written · {reread} of them read again"
    return " · ".join([line, *retired])


def _judge_line(events: list[JournalEvent]) -> str:
    """How often the compliance judge ran, and what came of it.

    A dispatch with no completion is a run that never came back — the case that
    used to look identical to a judge deciding to skip."""
    dispatched = sum(1 for event in events if event.event == JUDGING)
    finished = [event for event in events if event.event == JUDGED]
    if not dispatched and not finished:
        return ""
    missed = _unfinished(dispatched, finished)
    parts = [f"judge    {len(finished) + missed} run(s)", *_judged_counts(finished)]
    if missed > 0:
        parts.append(f"{missed} never came back")
    return " · ".join(parts)


def _unfinished(dispatched: int, finished: list[JournalEvent]) -> int:
    """Dispatches with no completion.

    Either end can fall outside the selected window on its own — a run starting
    at 23:59:59 and finishing after midnight has its dispatch excluded — so the
    run count above adds the two halves rather than trusting the dispatch count.
    """
    return max(0, dispatched - len(finished))


def _judged_counts(finished: list[JournalEvent]) -> list[str]:
    """What the completed runs did: made a journal call, skipped, or failed."""
    counts = [
        f"{sum(1 for event in finished if event.tool_calls)} with a call",
        f"{sum(1 for e in finished if e.tool_calls == 0 and not e.failed)} skipped",
    ]
    failed = sum(1 for event in finished if event.failed)
    if failed:
        counts.append(f"{failed} failed")
    return counts


def _is_read_after(events: list[JournalEvent], written: JournalEvent) -> bool:
    return any(
        event.event == READ
        and event.note == written.note
        and event.timestamp > written.timestamp
        for event in events
    )


def _never_read_line(events: list[JournalEvent], titles: dict[str, str] | None) -> str:
    injected = {
        note for event in events if event.event == INJECTED for note in event.hud
    }
    if not injected:
        return ""
    used = {event.note for event in events if event.event == READ}
    used.update(
        note for event in events if event.event == SEARCHED for note in event.hits
    )
    idle = sorted(injected - used)
    if not idle:
        return ""
    known = get_note_titles() if titles is None else titles
    names = [_title(known.get(note)) for note in idle]
    shown = "; ".join(names[:_NEVER_READ_SHOWN])
    more = len(names) - _NEVER_READ_SHOWN
    suffix = f"; +{more} more" if more > 0 else ""
    return (
        f"HUD      {len(idle)} of {len(injected)} injected note(s) never read or "
        f"searched for: {shown}{suffix}"
    )


def _title(title: str | None) -> str:
    if title is None:
        return _REMOVED
    if len(title) <= _TITLE_WIDTH:
        return title
    return title[: _TITLE_WIDTH - 1] + "…"


def _bytes(count: int) -> str:
    if count >= 1024:
        return f"{count / 1024:.1f} kB"
    return f"{count} B"
