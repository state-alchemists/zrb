"""A note's expiry: the condition it holds under, and how it is retired.

A finding used to have a birth and no end — its Context was written once and
never re-read — so a disproved claim stayed in every turn's context until
somebody noticed. The frontmatter now says when the finding stops applying, and
`SupersedeJournalNote` retires it while keeping the evidence.
"""

import os
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
        # Off here so these tests stay fast and independent of a `git` binary —
        # test_journal_git.py exercises git-backing.
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        yield str(root)


def _read(*parts) -> str:
    with open(os.path.join(*parts), "r", encoding="utf-8") as f:
        return f.read()


def test_a_note_says_when_it_stops_applying(writable_journal):
    """The condition is what makes a note retirable: a finding nobody wrote the
    expiry of can only be re-read, never checked."""
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="technical",
        slug="prebuffer",
        title="The cushion is a setting",
        context="While zrb ships the pocket engine",
        finding="A sentence starts on a cushion of audio",
        source="pcm_player.py:1",
        applies_when="while pocket stays the default speech engine",
    )

    note = _read(writable_journal, "technical/prebuffer.md")
    assert "applies_when: while pocket stays the default speech engine" in note
    assert "status: active" in note


def test_a_note_that_does_not_say_why_it_would_stop_is_refused(writable_journal):
    """The condition stopped being optional: a finding nobody wrote the expiry of
    can only be re-read, and 111 notes saying `not stated` is what that costs."""
    from zrb.llm.tool.journal_write import write_journal_note

    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="technical",
            slug="vague",
            title="T",
            context="c",
            finding="f",
            source="s",
        )

    assert str(excinfo.value).startswith("[SYSTEM SUGGESTION]")
    assert "a later session can check" in str(excinfo.value)
    assert not os.path.isfile(os.path.join(writable_journal, "technical/vague.md"))


def test_the_placeholder_an_old_writer_stored_is_not_a_condition(writable_journal):
    """`not stated` is read — an older note carrying it still loads — but writing
    it back is refused, so the placeholder cannot spread to a new note."""
    from zrb.llm.tool.journal_write import write_journal_note

    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="technical",
            slug="vague",
            title="T",
            context="c",
            finding="f",
            source="s",
            applies_when="not stated",
        )

    assert "placeholder" in str(excinfo.value)
    assert not os.path.isfile(os.path.join(writable_journal, "technical/vague.md"))


def test_superseding_takes_the_line_out_of_the_index_and_keeps_the_file(
    writable_journal,
):
    """A note that stopped applying costs every turn it stays in the index; its
    evidence is what keeps the journal able to explain itself."""
    from zrb.llm.tool.journal_write import (
        supersede_journal_note,
        write_journal_note,
    )

    write_journal_note(
        category="technical",
        slug="old-cause",
        title="Stutter comes from GIL contention",
        context="c",
        finding="f",
        source="s",
        hud_line="Stutter comes from GIL contention.",
        applies_when="until the decode timings are measured",
    )
    assert "Stutter comes from GIL contention." in _read(writable_journal, "index.md")

    result = supersede_journal_note(
        "technical", "old-cause", "superseded by the prebuffer note: it was a cushion"
    )

    index = _read(writable_journal, "index.md")
    assert "Stutter comes from GIL contention." not in index
    # The root index is what is injected, so nothing of the note stays in it;
    # the category index keeps the link, because the note still exists.
    assert "old-cause" not in index
    assert "old-cause" in _read(writable_journal, "technical/index.md")
    note = _read(writable_journal, "technical/old-cause.md")
    assert "status: superseded" in note
    assert "superseded by the prebuffer note: it was a cushion" in note
    assert "Removed from the index" in result


def test_a_slug_that_climbs_out_of_its_category_is_refused(writable_journal):
    """A slug is free text interpolated into a path, so `../index` is not a note
    name — joining it lands on the root index and the tool would write frontmatter
    into a file it never meant to touch."""
    from zrb.llm.tool.journal_write import (
        delete_journal_note,
        supersede_journal_note,
        write_journal_note,
    )

    write_journal_note(
        "technical", "real-note", "T", "c", "f", "s",
        applies_when="while zrb 3.29 is released",
    )
    index = _read(writable_journal, "index.md")

    for call in (
        lambda: supersede_journal_note("technical", "../index", "retired"),
        lambda: delete_journal_note("technical", "../index"),
    ):
        with pytest.raises(ValueError, match="kebab-case"):
            call()

    assert _read(writable_journal, "index.md") == index


def test_the_journal_tools_are_reachable_from_the_package(writable_journal):
    """The lazy package is the public API for a Python caller; a tool registered
    for the model but missing here is an ImportError away from unusable."""
    from zrb.llm.tool import delete_journal_note, supersede_journal_note

    assert callable(supersede_journal_note)
    assert callable(delete_journal_note)
