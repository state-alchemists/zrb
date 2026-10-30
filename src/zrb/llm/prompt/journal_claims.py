"""The claims a session is handed after its first turn.

The index goes in once, at the start, and a note written after that is invisible
until the conversation is compacted — so a session can record a fact and then
answer as though it never had it. This module picks what to show instead: a few
claims a turn, the ones most likely to matter now, and never a claim this
session has already been given.

A *claim* is the note's `hud_line`, which is why the line is a required argument
of every write: it is the only part of a note that can be shown cheaply, and a
note whose claim is missing cannot be injected at all.

Pure: notes in, notes out. No `CFG`, no I/O, so the caller owns both.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # A runtime import of `zrb.llm.tool` here would close a package cycle: two
    # tool modules read `zrb.llm.prompt.prompt`.
    from zrb.llm.tool.journal_note import Note

# Words too common to say what a turn is about. Short words go with them: a
# claim and a question share "the" in every message and nothing else.
_FILLER = frozenset(
    """a an and are as at be been but by can could did do does for from had has
    have how if in into is it its just like me my no not of on or our so than
    that the their them then there these they this to was we were what when
    where which who why will with would you your""".split()
)
# A word has to be this long to carry a subject: "fix" and "add" are verbs every
# turn has.
_MIN_TERM = 4
_TERM_RE = re.compile(r"[a-z0-9_]+")
# A pinned claim holds every turn, so it outranks an unpinned one written at the
# same moment. The weight is the multiplier, not a bonus, so it cannot be beaten
# by a handful of shared words.
PIN_WEIGHT = 2.0
_HALF_LIFE_DAYS = 1.0
_SECONDS_PER_DAY = 86400.0


def terms(text: str | None) -> set[str]:
    """The words of *text* a claim can share: lower-case, no filler, no short ones."""
    if not text:
        return set()
    return {
        word
        for word in _TERM_RE.findall(text.lower())
        if len(word) >= _MIN_TERM and word not in _FILLER
    }


def claim_score(note: Note, now: datetime, query: set[str]) -> float:
    """What this claim is worth injecting now; higher is better.

    Freshness dominates, because the notes this session has not been shown are
    the ones written during it: a note from last week is not what the turn is
    about, and `SearchJournal` is what finds those. A pin multiplies, because a
    pinned claim is a constraint that has to keep holding — one written this
    session must reach the next turn. Words shared with the message multiply
    again, so among notes written together the ones on the subject take the few
    slots there are.
    """
    age = max(0.0, (now - note.updated).total_seconds()) / _SECONDS_PER_DAY
    freshness = 0.5 ** (age / _HALF_LIFE_DAYS)
    shared = len(terms(f"{note.hud_line} {note.title} {note.keywords}") & query)
    return freshness * (1.0 + PIN_WEIGHT * note.pinned) * (1.0 + shared)


def select_claims(
    notes: list[Note],
    *,
    now: datetime,
    query: set[str],
    already: set[str],
    since: datetime | None = None,
    per_turn: int,
    max_chars: int,
) -> list[Note]:
    """The claims to inject this turn, highest score first.

    *already* holds the `category/slug` of every note this session has been
    shown as it then stood. *since* is when the session began: a claim is what
    the turn has just learned, so a note written before that is old news however
    it scored — it is what `SearchJournal` and the category indexes are for, and
    letting it through would spend one of three slots on it while the block's own
    sentence says otherwise. `None` means the log holds nothing for this session,
    so nothing is stale by comparison.

    *per_turn* and *max_chars* are both budgets and both apply: *per_turn* keeps
    a turn that wrote ten notes from dumping ten claims on the next one, and
    *max_chars* keeps one long claim from spending the whole allowance. A claim
    whose line does not fit is skipped rather than ending the turn, because the
    next line may be short.
    """
    if per_turn <= 0 or max_chars <= 0:
        return []
    candidates = [
        note
        for note in notes
        if note.is_active
        and note.hud_line
        and f"{note.category}/{note.slug}" not in already
        and (since is None or note.updated.astimezone(timezone.utc) >= since)
    ]
    ranked = sorted(
        candidates, key=lambda note: (-claim_score(note, now, query), note.rel)
    )
    chosen: list[Note] = []
    used = 0
    # Deferred: `zrb.llm.tool` reads `zrb.llm.prompt.prompt`, so a module-level
    # import here would make the two packages import each other.
    from zrb.llm.tool.journal_index import hud_line_of

    for note in ranked:
        size = len(hud_line_of(note)) + 1
        if used + size > max_chars:
            continue
        chosen.append(note)
        used += size
        if len(chosen) >= per_turn:
            break
    return chosen
