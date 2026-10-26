"""The root index lists newest first and caps its `## Recent Insights` catalog.

HUD sections render newest `updated` first so the injected snapshot, which is cut
from the end, loses the oldest lines. The catalog lists the newest N active notes
and one generated line counting the rest; the category indexes stay complete.
"""

import os
from unittest.mock import patch

import pytest

from zrb.llm.prompt.live_context import render_journal_index
from zrb.llm.tool import journal_write
from zrb.llm.tool.journal_write import (
    log_activity,
    supersede_journal_note,
    write_journal_note,
)

OLDER_LINE = "- _{n} older notes: see each category's index_"


@pytest.fixture
def writable_journal(tmp_path):
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 25
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        yield str(root)


def _read(root: str, relative: str = "index.md") -> str:
    with open(os.path.join(root, relative), "r", encoding="utf-8") as f:
        return f.read()


def _edit(root: str, old: str, new: str) -> None:
    text = _read(root)
    assert old in text
    with open(os.path.join(root, "index.md"), "w", encoding="utf-8") as f:
        f.write(text.replace(old, new, 1))


def _section(root: str, name: str) -> list[str]:
    body = _read(root).split(f"## {name}\n", 1)[1].split("\n## ", 1)[0]
    return [line for line in body.splitlines() if line.strip()]


def _note(slug, hud_line=None, category="technical", **extra) -> str:
    return write_journal_note(
        category=category,
        slug=slug,
        title=slug.title(),
        context="c",
        finding="f",
        source="s",
        hud_line=hud_line,
        **extra,
    )


def _notes(count: int) -> None:
    for number in range(count):
        _note(f"n{number:02d}", f"Headline {number:02d}.")


def test_a_hud_section_lists_newest_first_around_foreign_lines(writable_journal):
    _note("a", "Line a.")
    _edit(writable_journal, "## Recent\n", "## Recent\n\n- Hand note.\n")
    _note("b", "Line b.")
    _edit(writable_journal, "- Line b.", "- Hand tail.\n- Line b.")

    _note("c", "Line c.")

    assert _section(writable_journal, "Recent") == [
        "- Hand note.",
        "- Hand tail.",
        "- Line c. ([note](technical/c.md))",
        "- Line b. ([note](technical/b.md))",
        "- Line a. ([note](technical/a.md))",
    ]


def test_the_catalog_lists_the_newest_notes_and_counts_the_rest(writable_journal):
    with patch.object(journal_write.CFG, "LLM_JOURNAL_CATALOG_MAX_ENTRIES", 3):
        _notes(5)

    assert _section(writable_journal, "Recent Insights") == [
        "- [N04](technical/n04.md)",
        "- [N03](technical/n03.md)",
        "- [N02](technical/n02.md)",
        OLDER_LINE.format(n=2),
    ]
    assert "- [N00](n00.md)" in _read(writable_journal, "technical/index.md")


def test_the_default_cap_keeps_25_notes(writable_journal):
    _notes(27)

    catalog = _section(writable_journal, "Recent Insights")

    assert len(catalog) == 26
    assert catalog[0] == "- [N26](technical/n26.md)"
    assert catalog[-1] == OLDER_LINE.format(n=2)


def test_a_cap_of_zero_lists_every_note_and_no_count_line(writable_journal):
    journal_write.CFG.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 0

    _notes(30)

    catalog = _section(writable_journal, "Recent Insights")
    assert len(catalog) == 30
    assert not any("older note" in line for line in catalog)


def test_no_count_line_when_nothing_is_cut(writable_journal):
    _notes(3)

    assert not any(
        "older note" in line for line in _read(writable_journal).splitlines()
    )


def test_one_older_note_reads_as_singular(writable_journal):
    journal_write.CFG.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 2

    _notes(3)

    assert _section(writable_journal, "Recent Insights")[-1] == (
        "- _1 older note: see each category's index_"
    )


def test_a_superseded_note_is_not_counted_among_the_older_ones(writable_journal):
    journal_write.CFG.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 2
    _notes(3)

    supersede_journal_note("technical", "n00", "Gone.")

    assert not any(
        "older note" in line for line in _section(writable_journal, "Recent Insights")
    )


def test_the_count_line_is_owned_so_rendering_is_idempotent(writable_journal):
    journal_write.CFG.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 2
    _notes(4)
    index = _read(writable_journal)

    log_activity("anything")
    _note("n03", "Headline 03.")
    _note("n02", "Headline 02.")
    _note("n03", "Headline 03.")

    assert _read(writable_journal).count("older notes") == 1
    log_activity("again")
    after = _read(writable_journal)
    log_activity("again")
    assert _read(writable_journal) == after
    assert index.count("older notes") == 1


def test_the_count_line_is_not_kept_as_a_foreign_line_when_nothing_is_cut(
    writable_journal,
):
    journal_write.CFG.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 1
    _notes(2)
    assert "1 older note:" in _read(writable_journal)

    journal_write.CFG.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 0
    log_activity("anything")

    assert "older note" not in _read(writable_journal)


def test_a_catalog_hand_line_stays_beside_the_count_line(writable_journal):
    journal_write.CFG.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 1
    _notes(2)
    _edit(writable_journal, "## Recent Insights\n", "## Recent Insights\n\n- Hand.\n")

    _note("n02", "Headline 02.")

    catalog = _section(writable_journal, "Recent Insights")
    assert catalog[0] == "- Hand."
    assert catalog.count("- _2 older notes: see each category's index_") == 1


def test_a_long_hud_line_is_written_and_the_result_asks_for_a_shorter_one(
    writable_journal,
):
    line = "x" * 161

    result = _note("long", line)

    assert "161 characters" in result
    assert "shorter" in result
    assert line in _read(writable_journal)


def test_a_line_at_the_limit_draws_no_warning(writable_journal):
    result = _note("ok", "x" * 160, applies_when="while tests run")

    assert result == "Wrote technical/ok.md"


def test_the_injected_snapshot_keeps_the_newest_recent_lines(
    writable_journal, tmp_path
):
    _notes(10)
    text = _read(writable_journal)
    limit = text.index("- Headline 07") + 5

    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = writable_journal
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = limit
        cfg.LLM_JOURNAL_AUTO_SEARCH_ENABLED = False

        result = render_journal_index()

    assert result is not None
    assert "Headline 09" in result
    assert "Headline 08" in result
    assert "Headline 00" not in result


def test_notes_with_the_same_hud_line_are_each_named_when_evicted(writable_journal):
    """The cap names what a write evicted by note, not by the line's words: each
    HUD line ends in a link to its own note, so two notes that share a headline
    are still two lines, and the second eviction is reported too."""
    with patch.object(journal_write.CFG, "LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION", 1):
        results = [
            write_journal_note(
                "technical",
                slug,
                f"Note {slug}",
                "c",
                "f",
                "s",
                hud_line="The same headline.",
            )
            for slug in ("first", "second", "third")
        ]

    assert "Evicted" not in results[0]
    assert "technical/first.md" in results[1]
    assert "technical/second.md" in results[2]
    assert "technical/first.md" not in results[2]
