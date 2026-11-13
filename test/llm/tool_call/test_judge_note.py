"""The one line the shell judge puts in an approval prompt (ADR-0141)."""

from zrb.llm.tool_call.judge_note import (
    JUDGE_CAUTION,
    JUDGE_DANGEROUS,
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
    assert read_judge_note("call-1") == (JUDGE_CAUTION, "discards uncommitted work")
    assert format_judge_line("call-1") == (
        "       ⚠ judged caution: discards uncommitted work\n"
    )


def test_each_level_gets_its_own_glyph():
    record_judge_note("safe", JUDGE_SAFE, "read-only listing")
    record_judge_note("dangerous", JUDGE_DANGEROUS, "runs a remote script")
    record_judge_note("unknown", JUDGE_UNKNOWN, "the judge did not finish")
    assert "⚖" in format_judge_line("safe")
    assert "🛑" in format_judge_line("dangerous")
    assert "❔" in format_judge_line("unknown")


def test_an_unrecorded_call_draws_nothing():
    assert format_judge_line(None) == ""
    assert format_judge_line("never-recorded") == ""


def test_a_reason_that_spans_lines_draws_one():
    """A model can answer with a newline; the prompt below it must still read
    as the command to check, not as more of the verdict."""
    record_judge_note("multiline", JUDGE_CAUTION, "deletes build/\n  with no undo\tnow")
    drawn = format_judge_line("multiline")
    assert _lines(drawn) == ["       ⚠ judged caution: deletes build/ with no undo now"]


def test_control_characters_cannot_redraw_the_prompt():
    record_judge_note("escapes", JUDGE_DANGEROUS, "\x1b[2Jwipes the screen first")
    drawn = format_judge_line("escapes")
    assert "\x1b" not in drawn
    assert _lines(drawn) == ["       🛑 judged dangerous: [2Jwipes the screen first"]


def test_a_long_reason_is_clamped():
    record_judge_note("long", JUDGE_CAUTION, "x" * (MAX_JUDGE_REASON_CHARS + 500))
    drawn = format_judge_line("long")
    assert len(drawn) < MAX_JUDGE_REASON_CHARS + 60


def test_an_empty_reason_still_names_the_level():
    record_judge_note("empty", JUDGE_CAUTION, "   ")
    assert format_judge_line("empty") == "       ⚠ judged: caution\n"


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
