"""The note value: frontmatter parsing and writing, and the ordering stamp."""

from datetime import datetime, timedelta

from zrb.llm.tool.journal_note import (
    HUD_LINE_MAX_CHARS,
    HUD_LINE_SOURCE_DERIVED,
    HUD_LINE_SOURCE_WRITTEN,
    Note,
    check_applies_when,
    compose_note,
    derive_hud_line,
    derive_keywords,
    list_notes,
    next_stamp,
    normalize_keywords,
    parse_frontmatter,
    read_note,
    resolve_hud_line,
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


def test_the_derived_line_is_the_first_sentence_of_the_finding():
    finding = "The cushion is a sentence of audio. It starts playback early."

    assert derive_hud_line(finding) == "The cushion is a sentence of audio."


def test_an_abbreviation_does_not_end_the_derived_line():
    """`e.g.` is a period followed by a space, which a naive split reads as the
    end of the sentence: the claim then stops mid-thought ("The value is e.g.")
    while reading as a finished statement."""
    finding = "The value is e.g. enabled for retries in 3.29.0. It is safe."

    assert derive_hud_line(finding) == (
        "The value is e.g. enabled for retries in 3.29.0."
    )


def test_a_title_or_an_initial_does_not_end_the_derived_line():
    """`Dr.` is followed by a capital, so the letter after the period cannot be
    what decides this on its own."""
    finding = "Ask Dr. Chen, or J. Doe, before changing the retry. It is safe."

    assert derive_hud_line(finding) == (
        "Ask Dr. Chen, or J. Doe, before changing the retry."
    )


def test_an_abbreviation_that_can_end_a_sentence_ends_it():
    """`etc.` is both: mid-sentence a lower-case word follows, at the end of a
    sentence a capital does. It cannot be decided from the word alone, so it
    falls through to the next-word rule — the reviewer's trigger."""
    finding = "Use etc. Next step is locking. More later."

    assert derive_hud_line(finding) == "Use etc."


def test_etc_inside_a_sentence_does_not_end_it():
    finding = "Retries back off, etc. and the lock stays held."

    assert derive_hud_line(finding) == finding


def test_a_lowercase_sentence_keeps_the_claim_whole():
    """A period followed by a lower-case word is a continuation, not a new
    sentence, so nothing qualifies and the finding is its own claim — a long
    line is honest, and `_cap_line` still bounds it."""
    finding = "the retry is broken. retry again with the lock held."

    assert derive_hud_line(finding) == finding


def test_a_finding_with_no_terminator_is_its_own_line():
    assert derive_hud_line("`retry_period` is read\nwithout a lock") == (
        "`retry_period` is read without a lock"
    )


def test_a_derived_line_is_capped_and_says_it_was_cut():
    """A note with no line of its own still reaches the index; the cap is what
    keeps one note from spending the section's budget."""
    line = derive_hud_line("word " * 100)

    assert len(line) <= HUD_LINE_MAX_CHARS
    assert line.endswith("…")
    assert line[: -1].rstrip().endswith("word"), "cut at a word boundary"


def test_a_written_line_is_never_replaced_by_a_derived_one():
    prior = {"hud_line": "Goes by Go.", "hud_line_source": HUD_LINE_SOURCE_WRITTEN}

    assert resolve_hud_line("", "Something else entirely.", prior) == (
        "Goes by Go.",
        HUD_LINE_SOURCE_WRITTEN,
    )


def test_a_line_written_before_the_field_existed_counts_as_written():
    """An old note carries no `hud_line_source`; its line is somebody's words, so
    it is kept rather than traded for a guess."""
    assert resolve_hud_line("", "A finding.", {"hud_line": "Old words."}) == (
        "Old words.",
        HUD_LINE_SOURCE_WRITTEN,
    )


def test_a_derived_line_is_regenerated_from_the_current_finding():
    prior = {"hud_line": "An old guess.", "hud_line_source": HUD_LINE_SOURCE_DERIVED}

    assert resolve_hud_line("", "A new finding.", prior) == (
        "A new finding.",
        HUD_LINE_SOURCE_DERIVED,
    )


def test_a_supplied_line_is_written_and_normalized():
    assert resolve_hud_line("  Spaced   out  ", "f", {}) == (
        "Spaced out",
        HUD_LINE_SOURCE_WRITTEN,
    )


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
        "hud_line": "",
        "keywords": "",
        "pinned": "",
        "updated": "2026-10-30T00:00:00.000000",
    }
    fields.update(overrides)
    return fields


def test_a_composed_note_records_where_its_line_came_from_and_its_keywords():
    text = compose_note("", "/notes/technical/x.md", "index.md", _fields(), [])

    head = parse_frontmatter(text)
    assert head["hud_line"] == "`retry_period` is read without a lock."
    assert head["hud_line_source"] == HUD_LINE_SOURCE_DERIVED
    assert head["keywords"] == "retry, policy"


def test_a_composed_note_with_no_keyword_left_omits_the_field():
    fields = _fields(slug="ab", title="Cd")
    head = parse_frontmatter(
        compose_note("", "/notes/technical/ab.md", "index.md", fields, [])
    )

    assert "keywords" not in head
