"""Tests for the day block injected into ``<live-context>``.

The block is what makes a fresh session resume: the departing agent's handover,
today's most important lines, and the week that led here, one line per day. These
tests pin the four things that could silently break it — the handover being
dropped, importance being ignored, the week losing its theme, and the cap being
blown.
"""

from datetime import date, timedelta
from unittest.mock import patch

from zrb.llm.prompt.live_context import (
    DAY_BLOCK_MAX_CHARS,
    DAY_LINE_COUNT,
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
    _write_day(
        tmp_path, TODAY, "# 2026-10-26\n\n- 09:00 · home · something happened · imp 5\n"
    )
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


def test_a_dotted_tag_written_before_the_normalization_still_reads(tmp_path):
    """A tag written before the writer normalized dots is parsed whole, and the
    whole tag leaves the text: `project:soda.local.` must not render `soda` with
    `local.` stranded in the line."""
    _write_day(
        tmp_path,
        YESTERDAY,
        "# yesterday\n\n"
        "- 09:00 — updated the docs. Files: — · project:soda.local.\n",
    )

    result = _render(tmp_path)

    assert result is not None
    week = result.split("## This week", 1)[1]
    assert f"- {YESTERDAY.isoformat()} — soda.local: updated the docs" in week
    assert "local." not in week.replace("soda.local", "")


def test_a_project_tag_without_importance_keeps_the_period_out_of_the_tag(tmp_path):
    """The line ends with a period whether or not it carries an `imp` key.

    The tag's character set therefore has to stop short of it: a capture that took
    any non-space character read `zrb.` and the week rendered `zrb.: …`."""
    _write_day(
        tmp_path,
        YESTERDAY,
        "# yesterday\n\n" "- 09:00 — updated the docs. Files: — · project:zrb.\n",
    )

    result = _render(tmp_path)

    assert result is not None
    week = result.split("## This week", 1)[1]
    assert f"- {YESTERDAY.isoformat()} — zrb: updated the docs" in week
    assert "zrb.:" not in week


def test_a_summary_that_mentions_the_format_is_not_read_as_metadata(tmp_path):
    """A summary is free text, so it can spell the fields the writer appends.

    Split at the first ` Files: ` and the day read `explained`; search the whole
    line for a project and the summary's own words named the day. Only the
    writer's suffix is metadata, and the writer's is always last."""
    _write_day(
        tmp_path,
        YESTERDAY,
        "# yesterday\n\n"
        "- 08:00 — explained Files: syntax · project:other to him. "
        "Files: — · project:zrb · imp 6.\n"
        "- 09:00 — a quieter line. Files: — · project:zrb · imp 2.\n",
    )

    result = _render(tmp_path)

    assert result is not None
    week = result.split("## This week", 1)[1]
    assert "— zrb: explained Files: syntax · project:other to him" in week
    assert "— other:" not in week, "the summary does not name the day's project"


def test_today_keeps_one_period_before_the_files_it_reports(tmp_path):
    """The suffix owns the period that ends the summary, so joining adds none.

    `_without_keys` rebuilds a line from its two halves; a version that added the
    period itself rendered every today line as `fixed the retry bug. . Files: —.`.
    """
    _write_day(
        tmp_path,
        TODAY,
        "# today\n\n- 09:00 — fixed the retry bug. Files: src/a.py.\n",
    )

    result = _render(tmp_path)

    assert result is not None
    assert "fixed the retry bug. Files: src/a.py." in result
    assert ". . Files:" not in result


def test_a_line_written_before_the_suffix_names_no_project(tmp_path):
    """A line with no `. Files: …` suffix predates the project field too.

    Its own words can mention one — `discussed the project:zrb migration` — and
    reading that as a tag would label the day after a subject it never had."""
    _write_day(
        tmp_path,
        YESTERDAY,
        "# yesterday\n\n- 09:00 — discussed the project:zrb migration. Nothing else.\n",
    )

    result = _render(tmp_path)

    assert result is not None
    week = result.split("## This week", 1)[1]
    assert "— discussed the project:zrb migration" in week
    assert "— zrb:" not in week


def test_the_week_names_each_day_by_what_it_was_mostly_about(tmp_path):
    """Yesterday's theme, not its most important line.

    Measured on 2026-11-02: the day was SODA from seven in the morning until
    noon, and its highest-ranked line was a 22:45 fix in another repository. A
    person remembers the day as "soda all morning", so the week line follows the
    count, not the rank."""
    _write_day(tmp_path, TODAY, "# today\n\n- 09:00 · home · today · imp 5\n")
    _write_day(
        tmp_path,
        YESTERDAY,
        "# yesterday\n\n"
        "- 09:00 — brought the stack up. Files: infra/. · project:soda · imp 4\n"
        "- 10:00 — registered the runner. Files: runner.toml · project:soda · imp 5\n"
        "- 11:00 — accepted the EULA. Files: — · project:soda · imp 4\n"
        "- 22:45 — fixed the inlining. Files: src/a.py · project:zrb · imp 8\n",
    )

    result = _render(tmp_path)

    assert result is not None
    week = result.split("## This week", 1)[1]
    assert f"- {YESTERDAY.isoformat()} — soda: " in week
    assert "zrb:" not in week


def test_a_day_with_no_project_still_gets_a_week_line(tmp_path):
    "A journal written before the project tag existed still has a week."
    _write_day(
        tmp_path,
        YESTERDAY,
        "# yesterday\n\n- 09:00 · home · an unlabelled day · imp 3\n",
    )

    result = _render(tmp_path)

    assert result is not None
    assert f"- {YESTERDAY.isoformat()} — " in result
    assert "an unlabelled day" in result


def test_a_week_line_drops_the_clock_the_paths_and_the_keys(tmp_path):
    _write_day(
        tmp_path,
        YESTERDAY,
        "# yesterday\n\n"
        "- 09:00 — brought the stack up. Files: bankai_init.py, README.md"
        " · project:soda · imp 4\n",
    )

    result = _render(tmp_path)

    assert result is not None
    week = result.split("## This week", 1)[1]
    assert "soda: brought the stack up" in week
    assert "09:00" not in week
    assert "bankai_init.py" not in week
    assert "imp 4" not in week


def test_yesterday_handover_is_used_when_today_has_none(tmp_path):
    """A session that starts before the day's first line must still find the
    handover left the night before."""
    _write_day(
        tmp_path,
        YESTERDAY,
        "# yesterday\n\n- 17:16 · office · parked: retry block · imp 9\n\n"
        "## Handover\n\nRead the open items note first.\n",
    )
    _write_day(tmp_path, TODAY, "# today\n\n- 00:10 · home · a late line · imp 3\n")

    result = _render(tmp_path)

    assert result is not None
    assert "Read the open items note first." in result


def test_a_handover_survives_a_weekend(tmp_path):
    """Friday's handover is still the newest one on Monday.

    Day lines read today and yesterday, but a weekend is two day files wide, so
    looking that far for the handover dropped exactly the note a Monday session
    needs most — and it is the one part no later reader can reconstruct."""
    friday = TODAY - timedelta(days=3)
    _write_day(
        tmp_path, friday, "# friday\n\n## Handover\n\nFinish the retry fix first.\n"
    )

    result = _render(tmp_path)

    assert result is not None
    assert "Finish the retry fix first." in result


def test_the_newest_handover_wins(tmp_path):
    "An older handover is the less current answer, wherever it sits in the window."
    _write_day(
        tmp_path, TODAY - timedelta(days=4), "# old\n\n## Handover\n\nOlder plan.\n"
    )
    _write_day(
        tmp_path, TODAY - timedelta(days=2), "# recent\n\n## Handover\n\nNewer plan.\n"
    )

    result = _render(tmp_path)

    assert result is not None
    assert "Newer plan." in result
    assert "Older plan." not in result


def test_a_handover_older_than_the_window_is_not_used(tmp_path):
    """Eight days back is a different week: what it said has been overtaken, and
    the block would be inventing a seam rather than reporting one."""
    _write_day(
        tmp_path,
        TODAY - timedelta(days=8),
        "# stale\n\n## Handover\n\nStale plan.\n",
    )
    _write_day(tmp_path, TODAY, "# today\n\n- 09:00 · home · today happened · imp 5\n")

    result = _render(tmp_path)

    assert result is not None
    assert "Stale plan." not in result
    assert "today happened" in result


def test_the_whole_block_respects_the_cap(tmp_path):
    long_line = "x" * 400
    _write_day(
        tmp_path,
        TODAY,
        "# today\n\n"
        + "\n".join(f"- 0{i}:00 · home · {long_line} · imp 9" for i in range(9))
        + "\n\n## Handover\n\n"
        + long_line * 4
        + "\n",
    )

    result = _render(tmp_path)

    assert result is not None
    assert len(result) <= DAY_BLOCK_MAX_CHARS, "the cap is on the whole block"
    assert result.startswith("<day>") and result.endswith("</day>")


def test_the_block_says_it_is_memory_rather_than_a_briefing(tmp_path):
    """The block lands in a user turn, where nothing else explains how to use it.

    Without this line the model reports what it read — "according to the day
    block" — which is the briefing the whole seam exists to avoid.
    """
    _write_day(tmp_path, TODAY, "# today\n\n- 09:00 · home · a line · imp 5\n")

    result = _render(tmp_path)

    assert result is not None
    assert "not a briefing" in result
    assert "never announce or recite" in result


def test_the_block_names_the_tool_that_writes_the_handover(tmp_path):
    """The writer is deferred, so the block is the one place that names it.

    A tool nobody is reminded of at the moment it is needed is a tool that does
    not get used: the section would keep arriving only when it is typed by hand.
    """
    _write_day(tmp_path, TODAY, "# today\n\n- 09:00 · home · a line · imp 5\n")

    result = _render(tmp_path)

    assert result is not None
    assert "WriteDayHandover" in result


def test_a_one_paragraph_handover_still_carries_its_words(tmp_path):
    """A handover written as one long paragraph keeps its text.

    Cutting at the last line break would fall back to the newline right after the
    heading, so the block would arrive with a heading and nothing under it — the
    failure that looks like success.
    """
    paragraph = (
        "Do not rebuild the sweep before it can prove it cannot lose an entry. " * 40
    )
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


def test_a_long_handover_still_leaves_the_day_lines_a_line_each(tmp_path):
    """The handover leads, but it may not fill the cap on its own.

    Measured on 2026-10-27: a migrated handover of about 2,300 characters produced
    a 1,484-character block with no Today and no Yesterday in it — the two sections
    the day tier exists for, kept out by the one section nothing can reconstruct.
    The handover still takes the larger share; it just cannot take all of it.
    """
    handover = "\n".join(
        f"handover line {index}, long enough that the section is far over the cap."
        for index in range(40)
    )
    _write_day(
        tmp_path,
        TODAY,
        "# today\n\n"
        "- 09:00 · home · today's line that must still arrive · imp 9\n\n"
        "## Handover\n\n" + handover,
    )
    _write_day(
        tmp_path,
        YESTERDAY,
        "# yesterday\n\n"
        "- 20:00 · home · yesterday's line that must still arrive · imp 8\n",
    )

    result = _render(tmp_path)

    assert result is not None
    assert len(result) <= DAY_BLOCK_MAX_CHARS
    assert result.index("From the last me") < result.index("## Today")
    assert "today's line that must still arrive" in result
    assert "yesterday's line that must still arrive" in result


def test_a_long_handover_of_short_lines_is_cut_on_a_line_break(tmp_path):
    """When whole lines are there to cut on, no line arrives half-written."""
    lines = [
        f"line {index} of the handover, short enough to stay whole."
        for index in range(80)
    ]
    _write_day(tmp_path, TODAY, "# today\n\n## Handover\n\n" + "\n".join(lines))

    result = _render(tmp_path)

    assert result is not None
    assert len(result) <= DAY_BLOCK_MAX_CHARS
    assert "…" not in result, "there was a line break to cut on"
    assert result.splitlines()[-2] in lines, "the last line kept is a whole line"


def test_a_handover_carries_the_day_it_was_written(tmp_path):
    """The window is a week long, so an undated handover reads as tonight's.

    A Friday handover shown on Wednesday without its date is not stale memory;
    it is a misdated one, which is worse."""
    _write_day(
        tmp_path,
        TODAY - timedelta(days=3),
        "# three days ago\n\n## Handover\n\nFinish the sweep first.\n",
    )
    _write_day(tmp_path, TODAY, "# today\n\n- 09:00 · home · a line · imp 5\n")

    result = _render(tmp_path)

    assert result is not None
    assert f"to the next me ({(TODAY - timedelta(days=3)).isoformat()})" in result
    assert "Finish the sweep first." in result


def test_a_missing_handover_says_so_instead_of_leaving_a_hole(tmp_path):
    """A session that left none leaves no trace of what it was doing.

    Saying so is the difference between a quiet block and a block that reads as
    complete: the next session can ask instead of assuming the thread carried on.
    """
    _write_day(tmp_path, TODAY, "# today\n\n- 09:00 · home · a line · imp 5\n")

    result = _render(tmp_path)

    assert result is not None
    assert "From the last me" in result
    assert "None was left" in result
