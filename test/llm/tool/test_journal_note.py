"""The note value: frontmatter parsing and writing, and the ordering stamp."""

from datetime import datetime, timedelta

from zrb.llm.tool.journal_note import (
    Note,
    list_notes,
    next_stamp,
    parse_frontmatter,
    read_note,
    set_frontmatter,
)


def _note(updated: datetime, has_stamp: bool = True) -> Note:
    return Note("user", "a", "A", "active", "", False, updated, has_stamp)


def test_a_value_keeps_the_colons_after_the_first():
    text = "---\napplies_when: while zrb 3.26: released\n---\n# T\n"

    assert parse_frontmatter(text) == {"applies_when": "while zrb 3.26: released"}


def test_an_unterminated_block_is_not_frontmatter():
    assert parse_frontmatter("---\nslug: a\n# T\n") == {}


def test_setting_a_key_replaces_it_in_place_and_appends_a_new_one():
    text = "---\nslug: a\nstatus: active\n---\n# T\n"

    updated = set_frontmatter(text, {"status": "superseded", "pinned": "true"})

    assert updated == "---\nslug: a\nstatus: superseded\npinned: true\n---\n# T\n"


def test_a_none_value_removes_the_key():
    text = "---\nslug: a\npinned: true\n---\n# T\n"

    assert set_frontmatter(text, {"pinned": None}) == "---\nslug: a\n---\n# T\n"


def test_setting_a_key_on_text_without_frontmatter_creates_the_block():
    assert set_frontmatter("# T\n", {"status": "active"}) == (
        "---\nstatus: active\n---\n# T\n"
    )


def test_the_next_stamp_outranks_every_note_even_when_the_clock_went_back():
    now = datetime(2026, 1, 1, 12, 0, 0)
    newest = _note(now + timedelta(hours=1))

    assert next_stamp([_note(now), newest], now) > newest.updated
    assert next_stamp([], now) == now
    assert next_stamp([_note(now, has_stamp=False)], now) == now


def test_a_page_without_a_slug_is_not_a_note(tmp_path):
    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "page.md").write_text("# My own page\n")
    (tmp_path / "user" / "index.md").write_text("# User\n")
    (tmp_path / "user" / "real.md").write_text("---\nslug: real\n---\n# Real\n")

    notes = list_notes(str(tmp_path), ("index.md",))

    assert read_note(str(tmp_path), "user", "page.md") is None
    assert [note.rel for note in notes] == ["user/real.md"]
    assert notes[0].is_active
    assert not notes[0].is_migrated
