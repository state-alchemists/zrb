"""The notes a write sits beside, so the advice it contradicts is in front of it.

A note is written on its own, and the note it makes wrong is usually one the
writer never opened: a CI note can keep saying "re-run the failed job" after
another write has shown that a re-run repeats the failure. Nothing is missing
from the journal — the two notes simply never met.

So a write is answered with its neighbours: the few notes that share the words
this one is about. It is a hint, not a ranking, because the writer still has to
decide whether a neighbouring note is now wrong; and it reuses `terms`, the word
extraction the claims block already ranks by, so "about the same thing" means
one thing in this codebase rather than two.

Pure: notes in, notes out. No `CFG`, no I/O, so the caller owns both.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.prompt.journal_claims import terms

if TYPE_CHECKING:
    # A runtime import of `zrb.llm.tool` here would close a package cycle: two
    # tool modules read `zrb.llm.prompt.prompt`.
    from zrb.llm.tool.journal_note import Note


@dataclass(frozen=True)
class Written:
    """The note just written, as the neighbour search sees it.

    Its claim is deliberately absent: two claims share words when the two notes
    are about the same thing anyway, and a claim is the one field whose words are
    about the *fact* rather than the *subject*."""

    rel: str
    title: str
    keywords: str


# How many subject words two notes must share to be neighbours. One shared word
# is adjacent ("Note first" and "Note third" share "note"), two is the same
# subject — and a hint that fires on a single ordinary word fires on almost every
# write, which is how a hint stops being read.
_MIN_SHARED = 2


def nearby_notes(notes: list[Note], written: Written, limit: int) -> list[Note]:
    """The *limit* notes nearest *written*, the most shared words first.

    A retired note is not a neighbour: it is evidence, and telling a writer to
    revise it would undo the retirement the journal exists to record. The note
    being written is excluded too — a revision must not be handed back to itself
    as the thing it sits beside.

    *limit* `<= 0` answers nothing, for a caller that has turned the hint off.
    """
    if limit <= 0:
        return []
    wanted = _words(written.rel, written.title, written.keywords)
    scored = [
        (shared, note)
        for note in notes
        if note.is_active
        and note.rel != written.rel
        and (shared := len(_words(note.rel, note.title, note.keywords) & wanted))
        >= _MIN_SHARED
    ]
    scored.sort(key=lambda pair: (-pair[0], pair[1].rel))
    return [note for _, note in scored[:limit]]


def _words(rel: str, title: str, keywords: str) -> set[str]:
    """What a note is *about*: its own name, its title, and its keywords.

    Not its finding or its claim. Every note states a fact, and the facts shared
    between two notes is what `SearchJournal` answers; a name, a title and a
    keyword list are what an author chose as the note's subject, which is the
    question here — "is this the same subject as what I just wrote".

    The category is left out on purpose: every note filed under `technical` shares
    that word, so counting it would make every technical note every other one's
    neighbour.
    """
    name = rel.rsplit("/", 1)[-1].removesuffix(".md")
    return terms(" ".join(field.replace("-", " ") for field in (name, title, keywords)))
