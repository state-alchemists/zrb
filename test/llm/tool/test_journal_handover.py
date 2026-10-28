"""Tests for `WriteDayHandover`, the only writer of the day block's first section.

The reading end is pinned next door in
`test/llm/prompt/test_live_context_day_block.py`; these pin the writing end: one
section, rewritten rather than appended, under the day's lines and above its
`## Open` list, refused rather than truncated when it would eat the block.
"""

import os
from datetime import date
from unittest.mock import patch

import pytest


@pytest.fixture
def writable_journal(tmp_path):
    """Patch CFG for the writer module and return the journal root."""
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 25
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        yield str(root)


def _day_path(root: str) -> str:
    today = date.today()
    return os.path.join(
        root,
        "activity-log",
        today.strftime("%Y"),
        today.strftime("%Y-%m"),
        f"{today.isoformat()}.md",
    )


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _render(root: str) -> "str | None":
    """The block a fresh session would read, against the same journal root."""
    from zrb.llm.prompt.live_context import render_day_block

    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_ENABLED = True
        cfg.LLM_JOURNAL_DIR = root
        return render_day_block(date.today())


def test_the_handover_lands_where_the_next_session_reads_it(writable_journal):
    """The writer and the block's reader agree on the file and on the heading.

    Nothing wrote this section before, so a fresh session could only ever read
    the one file it was typed into by hand. This pins the two ends together.
    """
    from zrb.llm.tool.journal_write import write_day_handover

    write_day_handover("The sweep is unbuilt. Settle the tag before anything else.")

    block = _render(writable_journal)

    assert block is not None, "the block must find the file the writer wrote"
    assert "From the last me, to the next me" in block
    assert "Settle the tag before anything else." in block


def test_a_second_handover_replaces_the_first(writable_journal):
    """Rewritten, not appended: two sections would make the block pick one."""
    from zrb.llm.tool.journal_write import write_day_handover

    write_day_handover("first version, still deciding")
    write_day_handover("second version, decided")

    day = _read(_day_path(writable_journal))

    assert day.count("## Handover") == 1
    assert "first version" not in day
    assert "second version, decided" in day


def test_the_handover_sits_under_the_day_lines_and_above_backlinks(writable_journal):
    from zrb.llm.tool.journal_write import log_activity, write_day_handover

    log_activity("a day line that keeps its place")
    write_day_handover("where the work stopped")

    day = _read(_day_path(writable_journal))

    assert day.index("a day line that keeps its place") < day.index("## Handover")
    assert day.index("## Handover") < day.index("## Backlinks")


def test_an_open_list_survives_and_the_handover_goes_above_it(writable_journal):
    """A hand-written `## Open` is not the writer's to drop."""
    from zrb.llm.tool.journal_write import write_day_handover

    path = _day_path(writable_journal)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            f"# {date.today().isoformat()}\n\n"
            "- 09:00 — a line.\n\n"
            "## Open\n\n- [ ] the tag\n\n"
            "## Backlinks\n\n- [month index](index.md)\n"
        )

    write_day_handover("read the open list first")

    day = _read(path)

    assert day.count("## Open") == 1
    assert day.index("## Handover") < day.index("## Open")
    assert "read the open list first" in day
    assert "- [ ] the tag" in day


def test_an_over_long_handover_is_refused_rather_than_truncated(writable_journal):
    """A truncated handover arrives as if it were the whole one.

    The block cuts a long handover at read time, so a writer that also cut it
    would hide which end lost the tail, and the model would believe it had said
    the last thing it wrote.
    """
    from zrb.llm.tool.journal_write import HANDOVER_MAX_CHARS, write_day_handover

    with pytest.raises(ValueError) as raised:
        write_day_handover("x" * (HANDOVER_MAX_CHARS + 1))

    message = str(raised.value)
    assert "[SYSTEM SUGGESTION]" in message
    assert str(HANDOVER_MAX_CHARS) in message
    assert not os.path.exists(_day_path(writable_journal)), "a refusal writes nothing"


def test_an_empty_handover_is_refused(writable_journal):
    from zrb.llm.tool.journal_write import write_day_handover

    with pytest.raises(ValueError) as raised:
        write_day_handover("   \n\n")

    assert "[SYSTEM SUGGESTION]" in str(raised.value)
    assert not os.path.exists(_day_path(writable_journal))


def test_a_handover_carrying_its_own_heading_is_refused(writable_journal):
    """A `#` line would end the section at the next read.

    The block's reader stops at a `## ` line and so would a rewrite, which would
    leave everything under it stranded in the day file with no heading saying
    where it came from.
    """
    from zrb.llm.tool.journal_write import write_day_handover

    with pytest.raises(ValueError) as raised:
        write_day_handover("## Today\n\nthe state, with a heading of its own")

    message = str(raised.value)
    assert "[SYSTEM SUGGESTION]" in message
    assert not os.path.exists(_day_path(writable_journal)), "a refusal writes nothing"


def test_a_handover_keeps_what_was_logged_since_the_last_one(writable_journal):
    """The bug of 2026-10-28: a second handover took the whole afternoon with it.

    `log_activity` used to add its line before the Backlinks block, which sits
    inside the handover section, so every rewrite deleted everything written
    since the previous handover — the one copy of those hours.
    """
    from zrb.llm.tool.journal_write import log_activity, write_day_handover

    log_activity("alpha line")
    write_day_handover("HANDOVER-FIRST")
    log_activity("beta line")
    write_day_handover("HANDOVER-SECOND")

    day = _read(_day_path(writable_journal))

    assert "alpha line" in day
    assert "beta line" in day
    assert day.index("beta line") < day.index("## Handover")
    assert "HANDOVER-FIRST" not in day
    assert "HANDOVER-SECOND" in day


def test_a_day_line_stranded_in_an_old_handover_is_rescued(writable_journal):
    """A file the old code already wrote keeps its lines on the next write."""
    from zrb.llm.tool.journal_write import write_day_handover

    path = _day_path(writable_journal)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            f"# {date.today().isoformat()}\n\n"
            "- 09:00 — an early line. Files: — · imp 4.\n\n"
            "## Handover\n\nan old handover\n\n"
            "- 15:16 — stranded inside the old section. Files: — · imp 6.\n\n"
            "## Backlinks\n\n- [month index](index.md)\n"
        )

    write_day_handover("the new one")

    day = _read(path)

    assert "stranded inside the old section" in day
    assert day.index("stranded inside the old section") < day.index("## Handover")
    assert "[recovered from a handover" in day, "the reading is left open, not settled"
    assert "an old handover" not in day


def test_a_step_of_the_old_handover_is_marked_rather_than_called_an_event(
    writable_journal,
):
    """A line the file cannot classify keeps both readings, and loses no text.

    Older versions allowed a handover to hold a step in exactly the shape
    `log_activity` writes, so a rewrite cannot tell it from a stranded event by
    looking. It is lifted into the day's lines — the copy has to survive — and
    marked, because reading a step as finished work is the one error that costs
    the next session its answer.
    """
    from zrb.llm.tool.journal_write import write_day_handover

    path = _day_path(writable_journal)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            f"# {date.today().isoformat()}\n\n"
            "## Handover\n\nwhere it stopped:\n\n"
            "- 12:34 — deploy is blocked. Files: app.py.\n\n"
            "## Backlinks\n\n- [month index](index.md)\n"
        )

    write_day_handover("HANDOVER-SECOND")

    day = _read(path)
    lifted = next(line for line in day.splitlines() if "deploy is blocked" in line)

    assert not lifted.startswith("#"), "it is a day line, not a heading"
    assert "- 12:34 — deploy is blocked. Files: app.py." in lifted, "text kept whole"
    assert "[recovered from a handover" in lifted
    assert day.index(lifted) < day.index("## Handover")


def test_a_line_from_before_files_were_named_is_rescued_too(writable_journal):
    """The older ending is still a day line: `· imp N`, with no `Files: …`."""
    from zrb.llm.tool.journal_write import write_day_handover

    path = _day_path(writable_journal)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            f"# {date.today().isoformat()}\n\n"
            "## Handover\n\nan old handover\n\n"
            "- 09:08 — office · a line from before Files: · imp 6\n\n"
            "## Backlinks\n\n- [month index](index.md)\n"
        )

    write_day_handover("the new one")

    day = _read(path)

    assert "a line from before Files:" in day
    assert day.index("a line from before Files:") < day.index("## Handover")
    assert "an old handover" not in day


def test_a_handover_step_opening_like_a_day_line_is_refused(writable_journal):
    """The section must not hold a line a rewrite would lift out of it.

    Telling a step from an event by reading the line cannot be made reliable: the
    same model writes both, so `- 12:34 — deploy is blocked. Files: app.py.` is a
    shape it produces in either place. The writer keeps the ambiguity out of the
    file instead of resolving it wrongly on the next rewrite — and a refusal
    leaves the earlier handover standing.
    """
    from zrb.llm.tool.journal_write import write_day_handover

    write_day_handover("HANDOVER-KEPT")

    with pytest.raises(ValueError) as raised:
        write_day_handover(
            "where it stopped:\n\n- 12:34 — deploy is blocked. Files: app.py."
        )

    assert "[SYSTEM SUGGESTION]" in str(raised.value)
    assert "HANDOVER-KEPT" in _read(_day_path(writable_journal))


def test_a_handover_may_still_list_steps(writable_journal):
    """The refusal is about the clock stamp, not about lists."""
    from zrb.llm.tool.journal_write import write_day_handover

    write_day_handover("where it stopped:\n\n- deploy is blocked at 12:34")

    assert "deploy is blocked at 12:34" in _read(_day_path(writable_journal))


def test_a_handover_written_before_the_refusal_keeps_its_stamp_only_step(
    writable_journal,
):
    """A file already holding such a step is read as a handover, not as events."""
    from zrb.llm.tool.journal_write import write_day_handover

    path = _day_path(writable_journal)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            f"# {date.today().isoformat()}\n\n"
            "- 09:00 — an early line. Files: — · imp 4.\n\n"
            "## Handover\n\nwhere it stopped:\n\n- 12:34 — deploy is blocked\n\n"
            "## Backlinks\n\n- [month index](index.md)\n"
        )

    write_day_handover("HANDOVER-SECOND")

    day = _read(path)

    assert "deploy is blocked" not in day, "a step is not an event of the day"
    assert "an early line" in day
    assert "HANDOVER-SECOND" in day
