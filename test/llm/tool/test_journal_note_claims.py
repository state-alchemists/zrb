"""A note's claim metadata: the line that represents it, and what replaced it.

Measured on 2026-10-30 in a real journal of 233 notes: 98 carried no `hud_line`
and 111 said `applies_when: not stated`, so most of the journal could not be
shown or retired. The line is now written by the caller and mandatory — a note
derives nothing — and a condition is required. `keywords` and `superseded_by`
are the two fields that make a note findable again and make its replacement
explicit.
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
LINE = "Retry is not concurrency-safe."


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
        hud_line=LINE,
        applies_when=CONDITION,
    )
    fields.update(extra)
    return write_journal_note(**fields)


def test_the_line_the_caller_wrote_is_what_the_file_stores(writable_journal):
    _write()

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")

    assert front["hud_line"] == LINE
    # Nothing tracks where a line came from any more: there is only one source.
    assert "hud_line_source" not in front


def test_a_rewrite_without_a_line_is_refused_and_names_the_one_it_would_lose(
    writable_journal,
):
    """The claim is the one thing the index shows, so an omission has to cost a
    correction rather than silently replacing the line with nothing."""
    _write()

    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="technical",
            slug="retry-policy",
            title="Retry policy",
            context="c",
            finding="The lock was added.",
            source="s:2",
            hud_line="",
            applies_when=CONDITION,
        )

    message = str(excinfo.value)
    assert "[SYSTEM SUGGESTION]" in message
    assert LINE in message
    assert (
        _frontmatter(writable_journal, "technical", "retry-policy.md")["hud_line"]
        == LINE
    )


def test_a_revision_replaces_the_line_it_restates(writable_journal):
    _write()

    _write(hud_line="The lock is held now.", finding="The lock was added.", source="s:2")

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")
    assert front["hud_line"] == "The lock is held now."


def test_the_pin_survives_a_revision_that_does_not_mention_it(writable_journal):
    """The pin belongs to the note, not to the call: a rewrite that says nothing
    about it keeps it, and only `pinned: false` unpins."""
    _write(pinned=True)

    _write(finding="The lock was added.", source="s:2")

    front = _frontmatter(writable_journal, "technical", "retry-policy.md")
    assert front["pinned"] == "true"


def test_a_revision_can_unpin(writable_journal):
    _write(pinned=True)

    _write(pinned=False)

    assert "pinned" not in _frontmatter(writable_journal, "technical", "retry-policy.md")


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
