"""A note's claim metadata: the line that represents it, and what replaced it.

Measured on 2026-10-30 in a real journal of 233 notes: 98 carried no `hud_line`,
so the always-injected index could never show them, and 111 said `applies_when:
not stated`, so nothing could retire them. So a note now gets a line even when the
caller writes none, the one line it stores says whether it was written or derived,
and a condition is required. `keywords` and `superseded_by` are the two fields that
make a note findable again and make its replacement explicit.
"""

import os
from unittest.mock import patch

import pytest

from zrb.llm.tool.journal_note import parse_frontmatter
from zrb.llm.tool.journal_write import (
    journal_transaction,
    supersede_journal_note,
    write_journal_note,
)

FINDING = "`retry_period` is read without a lock. Concurrent runs collide."
CONDITION = "while base_task.py reads it unlocked"


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


def _frontmatter(*parts: str) -> dict[str, str]:
    with open(os.path.join(*parts), "r", encoding="utf-8") as handle:
        return parse_frontmatter(handle.read())


def _write(slug: str = "retry-policy", **extra) -> str:
    fields = dict(
        category="technical",
        slug=slug,
        title="Retry policy",
        context="c",
        finding=FINDING,
        source="s:1",
        applies_when=CONDITION,
    )
    fields.update(extra)
    return write_journal_note(**fields)


def test_a_note_with_no_line_is_given_one_and_the_file_says_so(writable_journal):
    """The index could not show 98 of 233 notes; a derived line is what puts every
    note in it without asking the caller for a second summary."""
    _write()

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")

    assert front["hud_line"] == "`retry_period` is read without a lock."
    assert front["hud_line_source"] == "derived"


def test_a_line_the_caller_wrote_is_recorded_as_written(writable_journal):
    _write(hud_line="Retry is not concurrency-safe.")

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")

    assert front["hud_line"] == "Retry is not concurrency-safe."
    assert front["hud_line_source"] == "written"


def test_a_derived_line_never_overwrites_a_written_one(writable_journal):
    _write(hud_line="Retry is not concurrency-safe.")

    _write(finding="The lock was added.", source="s:2")

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")
    assert front["hud_line"] == "Retry is not concurrency-safe."
    assert front["hud_line_source"] == "written"
    assert "The lock was added." in open(
        os.path.join(writable_journal, "technical/retry-policy.md"), encoding="utf-8"
    ).read()


def test_a_derived_line_follows_the_finding_when_the_note_is_rewritten(
    writable_journal,
):
    """A derived line is this module's guess, so a changed Finding regenerates it
    rather than leaving a headline that describes what the note used to say."""
    _write()

    _write(finding="The lock was added. Nothing collides now.", source="s:2")

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")
    assert front["hud_line"] == "The lock was added."
    assert front["hud_line_source"] == "derived"


def test_the_written_line_keeps_its_pin_through_a_revision(writable_journal):
    _write(hud_line="Retry is not concurrency-safe.", pinned=True)

    _write(finding="The lock was added.", source="s:2")

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")
    assert front["pinned"] == "true"


def test_keywords_given_by_the_caller_are_stored_lower_case_on_one_line(
    writable_journal,
):
    _write(keywords=["Identity", "retry lock", "identity"])

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")

    assert front["keywords"] == "identity, retry lock"


def test_keywords_absent_are_derived_from_the_slug_and_the_title(writable_journal):
    _write()

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")

    assert front["keywords"] == "retry, policy"


def test_a_rewrite_that_names_no_keywords_keeps_the_ones_already_stored(
    writable_journal,
):
    _write(keywords=["lock", "concurrency"])

    _write(finding="The lock was added.", source="s:2")

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")
    assert front["keywords"] == "lock, concurrency"


def test_a_supersede_records_the_note_that_replaced_it(writable_journal):
    _write("old-cause", hud_line="Stutter comes from GIL contention.")
    _write("prebuffer", finding="The stutter is a cushion of audio.")

    result = supersede_journal_note(
        "technical", "old-cause", "the cause was a cushion", superseded_by="technical/prebuffer"
    )

    front = _frontmatter(writable_journal, "technical", "old-cause.md")
    assert front["superseded_by"] == "technical/prebuffer"
    assert front["status"] == "superseded"
    assert "Replaced by technical/prebuffer." in result


def test_a_supersede_with_no_replacement_keeps_no_back_link(writable_journal):
    _write("old-cause", hud_line="Stutter comes from GIL contention.")

    supersede_journal_note("technical", "old-cause", "it was never true")

    front = _frontmatter(writable_journal, "technical", "old-cause.md")
    assert "superseded_by" not in front
    assert front["status"] == "superseded"


def test_a_later_supersede_that_names_no_replacement_drops_the_back_link(
    writable_journal,
):
    _write("old-cause", hud_line="Stutter comes from GIL contention.")
    _write("prebuffer", finding="The stutter is a cushion of audio.")
    supersede_journal_note("technical", "old-cause", "a cushion", "technical/prebuffer")

    supersede_journal_note("technical", "old-cause", "a decode spike, not a cushion")

    assert "superseded_by" not in _frontmatter(
        writable_journal, "technical", "old-cause.md"
    )


def test_a_replacement_that_was_never_written_is_refused(writable_journal):
    """The journal only writes a link once its target is on disk; a back-link to a
    note nobody wrote points the next reader at nothing."""
    _write("old-cause", hud_line="Stutter comes from GIL contention.")

    with pytest.raises(ValueError) as excinfo:
        supersede_journal_note("technical", "old-cause", "stale", "technical/ghost")

    assert str(excinfo.value).startswith("[SYSTEM SUGGESTION]")
    assert "does not exist" in str(excinfo.value)
    assert _frontmatter(writable_journal, "technical", "old-cause.md")["status"] == (
        "active"
    )


def test_a_replacement_that_is_not_a_note_path_is_refused(writable_journal):
    _write("old-cause", hud_line="Stutter comes from GIL contention.")

    with pytest.raises(ValueError, match="is not a note path"):
        supersede_journal_note("technical", "old-cause", "stale", "prebuffer")


def test_a_replacement_in_an_unknown_category_is_refused(writable_journal):
    _write("old-cause", hud_line="Stutter comes from GIL contention.")

    with pytest.raises(ValueError, match="unknown category"):
        supersede_journal_note("technical", "old-cause", "stale", "elsewhere/prebuffer")


def test_a_transaction_write_needs_a_condition_too(writable_journal):
    """`journal_transaction` reaches the writer without the tool's own argument
    check, so the writer makes it as well."""
    with pytest.raises(ValueError) as excinfo:
        with journal_transaction() as transaction:
            transaction.write_note(
                "technical", "no-condition", "T", "c", "f", "s", hud_line="A line."
            )

    assert str(excinfo.value).startswith("[SYSTEM SUGGESTION]")
    assert not os.path.isfile(
        os.path.join(writable_journal, "technical/no-condition.md")
    )
