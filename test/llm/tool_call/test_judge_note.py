"""The one line the shell judge puts in an approval prompt (ADR-0141)."""

from zrb.llm.tool_call.judge_note import (
    JUDGE_CAUTION,
    JUDGE_DANGEROUS,
    JUDGE_GLYPHS,
    JUDGE_SAFE,
    JUDGE_UNKNOWN,
    MAX_JUDGE_REASON_CHARS,
    discard_judge_note,
    format_judge_line,
    read_judge_note,
    record_judge_note,
)


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line]


def test_a_recorded_verdict_reads_back_and_draws_one_line():
    record_judge_note("call-1", JUDGE_CAUTION, "discards uncommitted work")
    assert read_judge_note("call-1") == (
        JUDGE_CAUTION,
        "discards uncommitted work",
        "",
    )
    assert format_judge_line("call-1") == (
        "       🟡 judged caution: discards uncommitted work\n"
    )


def test_each_level_leads_with_its_own_circle():
    """The circle is for the glance; the level word beside it is for the reader
    who is deciding, and is still the thing the decision is made on."""
    record_judge_note("safe", JUDGE_SAFE, "read-only listing")
    record_judge_note("dangerous", JUDGE_DANGEROUS, "runs a remote script")
    record_judge_note("unknown", JUDGE_UNKNOWN, "the judge did not finish")
    assert format_judge_line("safe") == "       🟢 judged safe: read-only listing\n"
    assert "🟡 judged caution: " in format_judge_line("call-1")
    assert "🔴 judged dangerous: " in format_judge_line("dangerous")
    assert "⚪ judged unknown: " in format_judge_line("unknown")


def test_every_circle_is_wide_by_default():
    """A glyph may lead the line only if prompt_toolkit and the terminal agree on
    its width. These four are East Asian Wide, so both count two columns — the
    trap is a symbol made emoji by a variation selector, which is counted two
    and drawn one."""
    import unicodedata

    assert set(JUDGE_GLYPHS) == {
        JUDGE_SAFE,
        JUDGE_CAUTION,
        JUDGE_DANGEROUS,
        JUDGE_UNKNOWN,
    }
    for glyph in JUDGE_GLYPHS.values():
        assert len(glyph) == 1
        assert "\ufe0f" not in glyph
        assert unicodedata.east_asian_width(glyph) in ("W", "F")


def test_an_unrecorded_call_draws_nothing():
    assert format_judge_line(None) == ""
    assert format_judge_line("never-recorded") == ""


def test_a_reason_that_spans_lines_draws_one():
    """A model can answer with a newline; the prompt below it must still read
    as the command to check, not as more of the verdict."""
    record_judge_note("multiline", JUDGE_CAUTION, "deletes build/\n  with no undo\tnow")
    drawn = format_judge_line("multiline")
    assert _lines(drawn) == [
        "       🟡 judged caution: deletes build/ with no undo now"
    ]


def test_control_characters_cannot_redraw_the_prompt():
    record_judge_note("escapes", JUDGE_DANGEROUS, "\x1b[2Jwipes the screen first")
    drawn = format_judge_line("escapes")
    assert "\x1b" not in drawn
    assert _lines(drawn) == ["       🔴 judged dangerous: [2Jwipes the screen first"]


def test_a_long_reason_is_clamped():
    record_judge_note("long", JUDGE_CAUTION, "x" * (MAX_JUDGE_REASON_CHARS + 500))
    drawn = format_judge_line("long")
    assert len(drawn) < MAX_JUDGE_REASON_CHARS + 60


def test_an_empty_reason_still_names_the_level():
    record_judge_note("empty", JUDGE_CAUTION, "   ")
    assert format_judge_line("empty") == "       🟡 judged: caution\n"


def test_reading_does_not_consume_the_line():
    """A response handler can ask again for the same call; the line belongs on
    every prompt drawn for it."""
    record_judge_note("twice", JUDGE_SAFE, "rebuilds build/ from source")
    first = format_judge_line("twice")
    second = format_judge_line("twice")
    assert first == second != ""


def test_discarding_drops_the_line():
    record_judge_note("gone", JUDGE_SAFE, "read-only")
    discard_judge_note("gone")
    assert read_judge_note("gone") is None
    assert format_judge_line("gone") == ""


def test_discarding_an_absent_call_is_not_an_error():
    discard_judge_note("nothing-here")
    discard_judge_note(None)


def test_the_facts_it_judged_with_sit_between_the_level_and_the_reason():
    """The sentence is the model's; the facts are `git status` and the call's own
    arguments, so they are the half of the line a reader can check."""
    record_judge_note(
        "facts", JUDGE_CAUTION, "rewrites history", "sandbox off · 12 uncommitted"
    )
    assert format_judge_line("facts") == (
        "       🟡 judged caution (sandbox off · 12 uncommitted): rewrites history\n"
    )


def test_a_verdict_with_no_facts_keeps_the_old_line():
    record_judge_note("clean", JUDGE_SAFE, "read-only listing", "")
    assert format_judge_line("clean") == "       🟢 judged safe: read-only listing\n"


def test_a_level_with_no_reason_still_carries_the_facts():
    record_judge_note("bare", JUDGE_UNKNOWN, " ", "sandbox off")
    assert format_judge_line("bare") == "       ⚪ judged: unknown (sandbox off)\n"


def test_facts_that_span_lines_draw_one():
    record_judge_note(
        "spread", JUDGE_CAUTION, "deletes build/", "sandbox off\n12 uncommitted"
    )
    assert _lines(format_judge_line("spread")) == [
        "       🟡 judged caution (sandbox off 12 uncommitted): deletes build/"
    ]
