"""Each journal tool, and the index injection, leaves one event in the log."""

import asyncio
import json

import pytest

from zrb.config.config import CFG
from zrb.llm.journal_usage_log import (
    DELETED,
    INJECTED,
    READ,
    SEARCHED,
    SUPERSEDED,
    WRITTEN,
    note_hash,
    read_events,
)
from zrb.llm.prompt.live_context import render_journal_index
from zrb.llm.tool.file_read import read_file
from zrb.llm.tool.journal import find_in_journal, search_journal
from zrb.llm.tool.journal_write import (
    delete_journal_note,
    supersede_journal_note,
    write_journal_note,
)

SLUG = "prebuffer-cushion"
TITLE = "The cushion is a setting"
HUD = "Speech starts on a cushion of audio"


@pytest.fixture
def journal(tmp_path, monkeypatch):
    root = tmp_path / "notes"
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path / "usage"), raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_DIR", str(root), raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_ENABLED", True, raising=False)
    return root


def _write(slug: str = SLUG, hud_line: str | None = HUD) -> str:
    return write_journal_note(
        category="technical",
        slug=slug,
        title=TITLE,
        context="While pocket is the default engine",
        finding="A sentence starts on a cushion",
        source="pcm_player.py:1",
        hud_line=hud_line,
        applies_when="while pocket is default",
    )


def _events(kind: str):
    return [event for event in read_events() if event.event == kind]


def test_writing_a_note_records_a_hashed_written_event(journal):
    _write()

    (event,) = _events(WRITTEN)

    assert event.note == note_hash(f"technical/{SLUG}")


def test_superseding_and_deleting_record_their_own_events(journal):
    _write()
    _write("second-note", hud_line=None)

    supersede_journal_note("technical", SLUG, "no longer true")
    delete_journal_note("technical", "second-note")

    (superseded,) = _events(SUPERSEDED)
    (deleted,) = _events(DELETED)
    assert superseded.note == note_hash(f"technical/{SLUG}")
    assert deleted.note == note_hash("technical/second-note")


def test_a_refused_write_records_nothing(journal):
    with pytest.raises(ValueError):
        write_journal_note(
            category="nonsense",
            slug=SLUG,
            title=TITLE,
            context="c",
            finding="f",
            source="s",
        )

    assert read_events() == []


def test_a_search_records_its_size_and_the_notes_it_found(journal):
    _write()

    result = search_journal("cushion")

    (event,) = _events(SEARCHED)
    assert event.terms == 1
    assert event.results == len(result["results"]) > 0
    assert not event.is_zero_result
    assert note_hash(f"technical/{SLUG}") in event.hits


def test_a_search_that_finds_nothing_is_flagged(journal):
    _write()

    search_journal("zebra giraffe")

    (event,) = _events(SEARCHED)
    assert event.terms == 2
    assert event.is_zero_result
    assert event.hits == []


def test_a_search_that_fails_is_not_recorded_as_one_that_found_nothing(journal):
    _write()

    result = search_journal("(unclosed")

    assert "error" in result
    assert _events(SEARCHED) == []


def test_the_auto_search_of_a_first_message_is_not_the_agents_search(journal):
    _write()

    find_in_journal("cushion")

    assert _events(SEARCHED) == []


def test_reading_a_note_by_path_records_a_read(journal):
    _write()

    asyncio.run(read_file(str(journal / "technical" / f"{SLUG}.md")))

    (event,) = _events(READ)
    assert event.note == note_hash(f"technical/{SLUG}")


def test_a_refused_read_of_a_note_is_not_recorded_as_a_read(journal):
    """A note the read refuses (binary content, or past the size cap) returned
    an error, not its text, so the report must not count it as read."""
    _write()
    note = journal / "technical" / f"{SLUG}.md"
    note.write_bytes(b"binary \x00 content")

    result = asyncio.run(read_file(str(note)))

    assert result.startswith("Error")
    assert _events(READ) == []


def test_a_note_whose_first_line_starts_with_error_still_counts_as_read(journal):
    """Success is the read header, which always precedes the note's own text."""
    _write()
    note = journal / "technical" / f"{SLUG}.md"
    note.write_text("Error handling policy\nbody\n", encoding="utf-8")

    result = asyncio.run(read_file(str(note)))

    assert result.startswith("[File: ")
    (event,) = _events(READ)
    assert event.note == note_hash(f"technical/{SLUG}")


def test_reading_an_index_or_a_file_outside_the_journal_records_nothing(
    journal, tmp_path
):
    _write()
    elsewhere = tmp_path / "elsewhere.md"
    elsewhere.write_text("hello")

    asyncio.run(read_file(str(journal / "index.md")))
    asyncio.run(read_file(str(journal / "technical" / "index.md")))
    asyncio.run(read_file(str(elsewhere)))

    assert _events(READ) == []


def test_injecting_the_index_records_bytes_and_the_hud_notes_it_carried(journal):
    _write()

    block = render_journal_index()

    assert block is not None
    (event,) = _events(INJECTED)
    assert event.size == len(block.encode("utf-8"))
    assert event.hud == [note_hash(f"technical/{SLUG}")]
    assert not event.truncated


def test_a_capped_index_is_recorded_as_truncated(journal, monkeypatch):
    for number in range(6):
        _write(f"note-{number}", hud_line=f"{HUD} number {number}")
    monkeypatch.setattr(CFG, "LLM_JOURNAL_INDEX_MAX_CHARS", 200, raising=False)

    render_journal_index()

    (event,) = _events(INJECTED)
    assert event.truncated


def test_the_log_holds_no_title_slug_hud_line_or_query(journal):
    _write()
    search_journal("cushion engine")
    asyncio.run(read_file(str(journal / "technical" / f"{SLUG}.md")))
    render_journal_index()
    supersede_journal_note("technical", SLUG, "reason text")

    lines = [
        line
        for path in (journal.parent / "usage").glob("journal-*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(lines) >= 5
    for line in lines:
        json.loads(line)
        for secret in (TITLE, SLUG, "prebuffer", HUD, "cushion", "engine", "reason"):
            assert secret not in line


def test_a_log_that_cannot_be_written_does_not_fail_the_tool(journal, monkeypatch):
    blocked = journal.parent / "blocked"
    blocked.write_text("a file where a directory should be")
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(blocked), raising=False)

    assert _write().startswith("Wrote")
    assert "results" in search_journal("cushion")
    assert render_journal_index() is not None
