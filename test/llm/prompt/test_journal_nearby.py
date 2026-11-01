"""The notes a write sits beside.

A note is written against advice the writer never read, and that advice keeps
reaching later sessions for as long as nobody notices the two disagree. These
tests pin the hint that makes the disagreement visible at the moment the write
creates it: the notes nearest the one just written, by the words each is about.
"""

from datetime import datetime, timedelta

from zrb.llm.prompt.journal_nearby import Written, nearby_notes
from zrb.llm.tool.journal_note import STATUS_ACTIVE, STATUS_SUPERSEDED, Note

NOW = datetime(2026, 11, 1, 12, 0)


def _note(
    slug: str,
    title: str,
    keywords: str = "",
    category: str = "technical",
    status: str = STATUS_ACTIVE,
    hud_line: str = "",
) -> Note:
    return Note(
        category=category,
        slug=slug,
        title=title,
        status=status,
        hud_line=hud_line or title,
        pinned=False,
        updated=NOW - timedelta(days=1),
        has_stamp=True,
        keywords=keywords,
    )


def _written(title: str, keywords: str, slug: str, category: str = "technical") -> Written:
    return Written(rel=f"{category}/{slug}.md", title=title, keywords=keywords)


def test_the_note_it_sits_beside_is_named():
    """The measured failure: the Windows note kept saying "re-run the failed job"
    while a note in the same family said a re-run repeats the failure."""
    notes = [
        _note("windows-ci", "Windows CI red at Install dependencies", "windows,ci,poetry"),
        _note("speech-stream", "Speech reads a reply a sentence at a time", "speech,tts"),
    ]
    found = nearby_notes(
        notes,
        _written("Windows CI needs its poetry cache cleared", "windows,ci,cache", "windows-cache"),
        3,
    )
    assert [note.rel for note in found] == ["technical/windows-ci.md"]


def test_a_note_about_something_else_is_not_named():
    notes = [_note("windows-ci", "Windows CI red at Install dependencies", "windows,ci,poetry")]
    found = nearby_notes(
        notes,
        _written("Speech reads a reply a sentence at a time", "speech,tts", "speech-stream"),
        3,
    )
    assert found == []


def test_the_note_being_written_is_not_its_own_neighbour():
    """A revision reuses its slug; handing it back to itself would spend the line
    on the note the writer is already holding."""
    notes = [_note("windows-ci", "Windows CI red at Install dependencies", "windows,ci,poetry")]
    found = nearby_notes(
        notes,
        _written("Windows CI red at Install dependencies", "windows,ci,poetry", "windows-ci"),
        3,
    )
    assert found == []


def test_a_retired_note_is_not_named():
    """A superseded note is evidence: telling a writer to revise it would undo the
    retirement the journal exists to record."""
    notes = [
        _note(
            "windows-ci",
            "Windows CI red at Install dependencies",
            "windows,ci,poetry",
            status=STATUS_SUPERSEDED,
        )
    ]
    found = nearby_notes(
        notes,
        _written("Windows CI needs its poetry cache cleared", "windows,ci,cache", "windows-cache"),
        3,
    )
    assert found == []


def test_the_limit_holds_and_a_tie_breaks_on_the_name():
    """Two notes sharing two words each are equally near, so the name decides and
    the order is the same on every run; the one sharing a single word ranks below
    them and falls outside a limit of two."""
    notes = [
        _note("windows-ci", "Windows CI red at Install dependencies", "windows,ci,poetry"),
        _note("windows-cache", "Windows cache keeps an old interpreter", "windows,cache"),
        _note("poetry-lock", "Poetry lock churns on a patch bump", "poetry,lock"),
    ]
    written = _written("Windows poetry cache cleared", "windows,poetry,cache", "windows-cleared")
    found = nearby_notes(notes, written, 2)
    assert [note.rel for note in found] == [
        "technical/windows-cache.md",
        "technical/windows-ci.md",
    ]
    assert nearby_notes(notes, written, 0) == []
