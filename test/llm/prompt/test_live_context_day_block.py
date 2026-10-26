"""Tests for the day block injected into ``<live-context>``.

The block is what makes a fresh session resume: the departing agent's handover,
today's most important lines, and yesterday's two. These tests pin the three
things that could silently break it — the handover being dropped, importance
being ignored, and the cap being blown.
"""

from datetime import date, timedelta
from unittest.mock import patch

from zrb.llm.prompt.live_context import (
    DAY_BLOCK_MAX_CHARS,
    DAY_LINE_COUNT,
    YESTERDAY_LINE_COUNT,
    render_day_block,
)

TODAY = date(2026, 10, 26)
YESTERDAY = TODAY - timedelta(days=1)


def _write_day(root, day: date, body: str) -> None:
    """Write *body* as the activity log's file for *day*, which is the day tier."""
    month = root / "activity-log" / day.strftime("%Y") / day.strftime("%Y-%m")
    month.mkdir(parents=True, exist_ok=True)
    (month / f"{day.isoformat()}.md").write_text(body, encoding="utf-8")


def _render(root, today: date = TODAY) -> "str | None":
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_ENABLED = True
        cfg.LLM_JOURNAL_DIR = str(root)
        return render_day_block(today)


def test_the_block_reads_the_activity_log_that_log_activity_writes(tmp_path):
    """The day tier is the activity log's own day file, not a second layout.

    The block used to look in `days/`, which nothing writes, so it rendered
    nothing in normal use. This pins the two ends together: what the writer
    writes is what the reader finds, `imp N` and all.
    """
    from zrb.llm.tool.journal_write import log_activity

    with patch("zrb.llm.tool.journal_write.CFG") as writer_cfg:
        writer_cfg.LLM_JOURNAL_DIR = str(tmp_path)
        writer_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        writer_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        writer_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        writer_cfg.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 25
        writer_cfg.LLM_JOURNAL_GIT_ENABLED = False
        log_activity("wired the day tier to the activity log", importance=9)

    block = _render(tmp_path, date.today())
    assert block is not None, "the block must find the file LogActivity wrote"
    assert "wired the day tier to the activity log" in block
    assert "imp 9" not in block, "importance is a ranking key, not block text"


def test_no_day_file_renders_nothing(tmp_path):
    """A journal without a day tier must render exactly as it did before."""
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_ENABLED = True
        cfg.LLM_JOURNAL_DIR = str(tmp_path)
        assert render_day_block(TODAY) is None


def test_journal_disabled_renders_nothing(tmp_path):
    _write_day(tmp_path, TODAY, "# 2026-10-26\n\n- 09:00 · home · something happened · imp 5\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_ENABLED = False
        cfg.LLM_JOURNAL_DIR = str(tmp_path)
        assert render_day_block(TODAY) is None


def test_handover_leads_and_today_keeps_the_important_lines(tmp_path):
    """The handover is the point of the block; today is cut by importance, not
    by order, so a trivial evening line cannot push out the morning's constraint."""
    _write_day(
        tmp_path,
        TODAY,
        "# 2026-10-26 (Mon)\n\n"
        "- 08:00 · home · trivia nobody needs · imp 1\n"
        "- 09:00 · home · a constraint that must survive · imp 9\n"
        "- 10:00 · office · a detail · imp 4\n"
        "- 11:00 · office · another detail · imp 5\n"
        "- 12:00 · office · middle of the day · imp 6\n"
        "- 13:00 · office · afternoon · imp 7\n"
        "- 14:00 · office · one more · imp 3\n"
        "\n## Handover — tonight's me, for tomorrow's me\n\n"
        "You left him at the cafe. Do not re-propose the digest.\n\n"
        "## Open\n\n- [ ] something · imp 5\n",
    )

    result = _render(tmp_path)

    assert result is not None
    handover_at = result.index("From the last me")
    today_at = result.index("## Today")
    assert handover_at < today_at, "the handover must lead the block"
    assert "Do not re-propose the digest" in result
    assert "a constraint that must survive" in result
    assert "trivia nobody needs" not in result
    assert result.count("\n- ") == DAY_LINE_COUNT, "today contributes exactly the cap"
    assert "## Open" not in result, "an `##` section ends the entry list"


def test_yesterday_contributes_two_lines(tmp_path):
    _write_day(tmp_path, TODAY, "# today\n\n- 09:00 · home · today · imp 5\n")
    _write_day(
        tmp_path,
        YESTERDAY,
        "# yesterday\n\n"
        "- 09:00 · home · least important · imp 2\n"
        "- 10:00 · home · the one that matters · imp 8\n"
        "- 11:00 · home · middle · imp 5\n",
    )

    result = _render(tmp_path)

    assert result is not None
    assert f"## Yesterday ({YESTERDAY.isoformat()})" in result
    assert "the one that matters" in result
    assert "least important" not in result
    yesterday_rows = result.split("## Yesterday", 1)[1].count("\n- ")
    assert yesterday_rows == YESTERDAY_LINE_COUNT


def test_yesterday_handover_is_used_when_today_has_none(tmp_path):
    """A session that starts before the day's first line must still find the
    handover left the night before."""
    _write_day(tmp_path, YESTERDAY, "# yesterday\n\n- 17:16 · office · parked: retry block · imp 9\n\n"
                                   "## Handover\n\nRead the open items note first.\n")
    _write_day(tmp_path, TODAY, "# today\n\n- 00:10 · home · a late line · imp 3\n")

    result = _render(tmp_path)

    assert result is not None
    assert "Read the open items note first." in result


def test_the_whole_block_respects_the_cap(tmp_path):
    long_line = "x" * 400
    _write_day(
        tmp_path,
        TODAY,
        "# today\n\n"
        + "\n".join(f"- 0{i}:00 · home · {long_line} · imp 9" for i in range(9))
        + "\n\n## Handover\n\n" + long_line * 4 + "\n",
    )

    result = _render(tmp_path)

    assert result is not None
    assert len(result) <= DAY_BLOCK_MAX_CHARS, "the cap is on the whole block"
    assert result.startswith("<day>") and result.endswith("</day>")


def test_a_one_paragraph_handover_still_carries_its_words(tmp_path):
    """A handover written as one long paragraph keeps its text.

    Cutting at the last line break would fall back to the newline right after the
    heading, so the block would arrive with a heading and nothing under it — the
    failure that looks like success.
    """
    paragraph = "Do not rebuild the sweep before it can prove it cannot lose an entry. " * 40
    _write_day(
        tmp_path,
        TODAY,
        "# today\n\n- 09:00 · home · a line · imp 5\n\n## Handover\n\n" + paragraph,
    )

    result = _render(tmp_path)

    assert result is not None
    assert len(result) <= DAY_BLOCK_MAX_CHARS
    body = result.split("From the last me, to the next me", 1)[1]
    assert len(body.strip()) > 200, "the heading alone is not a handover"
    assert "Do not rebuild the sweep" in result


def test_a_long_handover_of_short_lines_is_cut_on_a_line_break(tmp_path):
    """When whole lines are there to cut on, no line arrives half-written."""
    lines = [f"line {index} of the handover, short enough to stay whole." for index in range(80)]
    _write_day(tmp_path, TODAY, "# today\n\n## Handover\n\n" + "\n".join(lines))

    result = _render(tmp_path)

    assert result is not None
    assert len(result) <= DAY_BLOCK_MAX_CHARS
    assert "…" not in result, "there was a line break to cut on"
    assert result.splitlines()[-2] in lines, "the last line kept is a whole line"
