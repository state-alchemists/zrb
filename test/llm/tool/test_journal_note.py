"""The note value: frontmatter parsing and writing, and the ordering stamp."""

from datetime import datetime, timedelta

import pytest

from zrb.llm.tool.journal_note import (
    Note,
    check_applies_when,
    check_slug,
    compose_note,
    derive_keywords,
    list_notes,
    next_stamp,
    normalize_keywords,
    one_line,
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


def test_a_line_is_stored_on_one_line():
    assert one_line("  Spaced   out  ") == "Spaced out"


def test_an_applies_when_that_states_nothing_is_refused():
    for value in (None, "", "   ", "not stated"):
        try:
            check_applies_when(value)
        except ValueError as error:
            assert str(error).startswith("[SYSTEM SUGGESTION]")
        else:  # pragma: no cover - the assertion below is the point
            raise AssertionError(f"{value!r} was accepted")


def test_an_applies_when_is_kept_on_one_line():
    assert check_applies_when("while zrb\n3.29 is released") == (
        "while zrb 3.29 is released"
    )


def test_keywords_come_from_the_slug_and_the_title():
    """A note nobody gave keywords to is still one a later session has to find."""
    keywords = derive_keywords("journal-claim-metadata", "A note claims its data")

    assert keywords == "journal, claim, metadata, note, claims, data"


def test_a_keyword_shorter_than_four_characters_is_left_out():
    assert derive_keywords("a-b", "Cat sat on the mat") == ""


def test_keywords_are_lower_case_comma_separated_and_unique():
    assert normalize_keywords([" Pocket ", "pocket", "", "Speech, engine"]) == (
        "pocket, speech, engine"
    )


def _fields(**overrides: str) -> dict[str, str]:
    fields = {
        "slug": "retry-policy",
        "title": "Retry policy",
        "context": "c",
        "finding": "`retry_period` is read without a lock. Runs collide.",
        "source": "s:1",
        "applies_when": "while base_task.py reads it unlocked",
        "status": "active",
        "hud_line": "A claim.",
        "keywords": "",
        "pinned": "",
        "updated": "2026-10-30T00:00:00.000000",
    }
    fields.update(overrides)
    return fields


def test_a_composed_note_writes_the_line_it_was_given_and_derives_keywords():
    text = compose_note(
        "", "/notes/technical/x.md", "index.md", _fields(hud_line="Runs collide."), []
    )

    head = parse_frontmatter(text)
    assert head["hud_line"] == "Runs collide."
    assert "hud_line_source" not in head
    assert head["keywords"] == "retry, policy"


def test_a_composed_note_with_no_keyword_left_omits_the_field():
    fields = _fields(slug="ab", title="Cd")
    head = parse_frontmatter(
        compose_note("", "/notes/technical/ab.md", "index.md", fields, [])
    )

    assert "keywords" not in head


@pytest.mark.parametrize("slug", ["a", "retry-policy", "v2-notes"])
def test_a_kebab_case_slug_is_accepted(slug):
    check_slug(slug)


@pytest.mark.parametrize("slug", ["retry-policy\n", "\n", "retry-policy\n\n", "../x"])
def test_a_slug_with_a_line_break_or_a_path_is_refused(slug):
    with pytest.raises(ValueError, match="kebab-case"):
        check_slug(slug)
