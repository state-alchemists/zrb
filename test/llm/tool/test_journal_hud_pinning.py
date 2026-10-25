"""The HUD section cap: what it drops, what it reports, and what survives.

`test_journal_hud_sections.py` covers where a line lands and how an old index
gains a section. This file covers the cap on top of that: an ordered list of
constraints sharing one section cannot grow forever, so a line eventually goes
— and the write used to report success while it went. A dropped line is now
named in the result, and a line marked `pinned=True` is only dropped once every
line in its section is pinned.
"""

import os
from unittest.mock import patch

import pytest

from zrb.llm.tool import journal_write
from zrb.llm.tool.journal_write import delete_journal_note, write_journal_note


@pytest.fixture
def writable_journal(tmp_path):
    """Patch CFG for the writer module and return the journal root."""
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        yield str(root)


def _read(root: str) -> str:
    with open(os.path.join(root, "index.md"), "r", encoding="utf-8") as f:
        return f.read()


def _hud_section(root: str, name: str) -> str:
    """The lines under `## <name>` in the root index."""
    return _read(root).split(f"## {name}", 1)[1].split("\n## ", 1)[0]


def _pin(slug: str, hud_line: str, pinned: bool = False) -> str:
    """Write one technical note, which pins its line under Active Constraints."""
    return write_journal_note(
        category="technical",
        slug=slug,
        title=slug.title(),
        context="c",
        finding="f",
        source="s",
        hud_line=hud_line,
        pinned=pinned,
    )


def test_an_eviction_is_named_in_the_write_result(writable_journal):
    """The model can only re-pin a line it is told about, so the result names
    what the cap dropped and says how to keep it next time."""
    journal_write.CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 2
    results = [
        write_journal_note(
            category="user",
            slug=f"pref-{i}",
            title="Preference",
            context="c",
            finding="f",
            source="s",
            hud_line=f"Preference number {i}.",
        )
        for i in range(3)
    ]

    # Nothing evicted, nothing added to the result.
    assert results[0] == "Wrote user/pref-0.md"
    assert results[1] == "Wrote user/pref-1.md"
    assert results[2].startswith("Wrote user/pref-2.md. Evicted from ## User (cap 2): ")
    assert '"Preference number 0. ([note](user/pref-0.md))"' in results[2]
    assert "pinned=True" in results[2]
    assert "LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION" in results[2]


def test_an_uncapped_section_evicts_nothing(writable_journal):
    """`<= 0` disables the cap, so nothing is lost and nothing is reported."""
    journal_write.CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 0
    results = [
        write_journal_note(
            category="user",
            slug=f"pref-{i}",
            title="Preference",
            context="c",
            finding="f",
            source="s",
            hud_line=f"Preference number {i}.",
        )
        for i in range(3)
    ]

    assert all("Evicted" not in result for result in results)
    section = _hud_section(writable_journal, "User")
    for i in range(3):
        assert f"Preference number {i}." in section


def test_a_pinned_line_survives_the_section_cap(writable_journal):
    """The oldest *unpinned* line goes first, so a durable constraint marked
    `pinned=True` outlives the lines written after it."""
    journal_write.CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 2
    _pin("public-tests", "Tests stay public-API only.", pinned=True)
    _pin("will-go", "A line that will go.")
    result = _pin("stays", "A line that stays.")

    section = _hud_section(writable_journal, "Active Constraints")
    assert "- 📌 Tests stay public-API only." in section
    assert "A line that will go." not in section
    assert "A line that stays." in section
    assert '"A line that will go. ([note](technical/will-go.md))"' in result


def test_when_every_line_is_pinned_the_oldest_pinned_line_is_evicted(
    writable_journal,
):
    """Pinning delays an eviction; it does not let a section grow forever. With
    nothing unpinned left to sacrifice the oldest pinned line goes, and the
    result names it rather than hiding it."""
    journal_write.CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 2
    _pin("first", "The first pinned line.", pinned=True)
    _pin("second", "The second pinned line.", pinned=True)
    result = _pin("third", "The third pinned line.", pinned=True)

    section = _hud_section(writable_journal, "Active Constraints")
    assert "The first pinned line." not in section
    assert "The second pinned line." in section
    assert "The third pinned line." in section
    assert "Evicted from ## Active Constraints (cap 2)" in result
    assert '"📌 The first pinned line. ([note](technical/first.md))"' in result


def test_pin_state_comes_from_the_argument_not_from_the_text(writable_journal):
    """A revision may hand the line back as it was read in the index, marker
    included. The marker is stripped first, so the argument decides."""
    _pin("retry-policy", "📌 Retry is not concurrency-safe.")

    section = _hud_section(writable_journal, "Active Constraints")
    assert "- Retry is not concurrency-safe. ([note](technical/retry-policy.md))" in (
        section
    )
    assert "📌" not in section


def test_deleting_a_pinned_note_removes_its_marked_line(writable_journal):
    """The scrub regex has to tolerate the marker a pin puts in front of the
    text, or a delete leaves a pinned line pointing at a file that is gone."""
    _pin("retracted", "A fact that is about to be retracted.", pinned=True)
    assert "- 📌 A fact that is about to be retracted." in _hud_section(
        writable_journal, "Active Constraints"
    )

    delete_journal_note("technical", "retracted")

    index = _read(writable_journal)
    assert "about to be retracted" not in index
    assert "technical/retracted.md" not in index


def test_two_notes_pinning_the_same_words_keep_one_line_each(writable_journal):
    """A line linked to another note is that note's, even when the words match.

    The text-equality fallback is for an unlinked copy. Applied to a linked line
    it deleted the first note's only route back from the index, so the second
    write quietly stole the first one's HUD entry.
    """
    for slug in ("first", "second"):
        write_journal_note(
            "user",
            slug,
            slug.title(),
            "ctx",
            "found",
            "s:1",
            hud_line="Prefers concise replies.",
        )

    section = _hud_section(writable_journal, "User")
    assert "([note](user/first.md))" in section
    assert "([note](user/second.md))" in section


def test_a_hud_line_echoing_another_notes_link_does_not_steal_its_line(
    writable_journal,
):
    """A caller may hand back the line it read, link included — and that link may
    be the other note's when both pinned the same words. Comparing the echoed
    text against the existing line matched, so the write deleted the first
    note's entry and the second one inherited its link.
    """
    write_journal_note(
        "user",
        "first",
        "First",
        "ctx",
        "found",
        "s:1",
        hud_line="Prefers terse replies.",
    )
    write_journal_note(
        "user",
        "second",
        "Second",
        "ctx",
        "found",
        "s:1",
        hud_line="Prefers terse replies. ([note](user/first.md))",
    )

    section = _hud_section(writable_journal, "User")
    own_first = [
        line
        for line in section.splitlines()
        if line.endswith("([note](user/first.md))")
    ]
    own_second = [
        line
        for line in section.splitlines()
        if line.endswith("([note](user/second.md))")
    ]
    # Each note keeps its own line...
    assert len(own_first) == 1
    assert len(own_second) == 1
    # ...and the echoed link is not copied onto the second one: it was read from
    # the index, not written, so it stays with the note it points at.
    assert "user/first.md" not in own_second[0]


def test_an_echoed_line_handed_back_with_its_bullet_is_still_an_echo(
    writable_journal,
):
    """A caller may repeat the index line verbatim: bullet, pin marker and link.

    The bullet is stripped when the line is first read (`_hud_line_text`), so
    echo detection compares prose to prose; the pin marker and the link are
    handled by the same normalization. What must not survive is the old note's
    link on the new note's line.
    """
    write_journal_note(
        "user",
        "first",
        "First",
        "ctx",
        "found",
        "s:1",
        hud_line="Prefers terse replies.",
    )
    write_journal_note(
        "user",
        "second",
        "Second",
        "ctx",
        "found",
        "s:1",
        hud_line="- 📌 Prefers terse replies. ([note](user/first.md))",
    )

    section = _hud_section(writable_journal, "User")
    own_second = [
        line
        for line in section.splitlines()
        if line.endswith("([note](user/second.md))")
    ]
    assert len(own_second) == 1
    assert "user/first.md" not in own_second[0]
    assert "📌" not in own_second[0]
    assert (
        sum(
            1
            for line in section.splitlines()
            if line.endswith("([note](user/first.md))")
        )
        == 1
    )
