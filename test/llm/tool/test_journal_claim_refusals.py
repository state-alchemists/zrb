"""What the writer refuses: a note with no finding, a replacement that is not a note."""

import os

import pytest

from zrb.config.config import CFG
from zrb.llm.tool.journal_write import supersede_journal_note, write_journal_note


@pytest.fixture
def journal_dir(tmp_path, monkeypatch):
    root = tmp_path / "notes"
    monkeypatch.setattr(CFG, "LLM_JOURNAL_DIR", str(root), raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_GIT_ENABLED", False, raising=False)
    return root


def _write(slug: str, finding: str = "A finding worth keeping.") -> None:
    write_journal_note(
        category="technical",
        slug=slug,
        title=f"Note {slug}",
        context="Why it came up.",
        finding=finding,
        hud_line=finding,
        source="a test",
        applies_when="while this test suite exists",
    )


def test_a_note_with_no_finding_is_refused_with_a_suggestion(journal_dir):
    """A note with no finding derives no claim, so it would never reach the
    injected index: written, and unreadable by the next session."""
    with pytest.raises(ValueError) as excinfo:
        _write("empty", finding="")

    message = str(excinfo.value)
    assert "[SYSTEM SUGGESTION]" in message
    assert "finding was empty" in message
    assert not os.path.exists(journal_dir / "technical" / "empty.md")


def test_a_new_note_with_no_line_is_refused_with_a_suggestion(journal_dir):
    """The line is the one thing the injected index shows, and nothing derives
    it any more: a note written without one would be a note no later session
    can see."""
    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="technical",
            slug="no-line",
            title="Note",
            context="Why it came up.",
            finding="A finding worth keeping.",
            source="a test",
            hud_line="",
            applies_when="while this test suite exists",
        )

    message = str(excinfo.value)
    assert "[SYSTEM SUGGESTION]" in message
    assert "hud_line was empty" in message
    assert not os.path.exists(journal_dir / "technical" / "no-line.md")


def test_a_supersede_cannot_point_at_a_page_that_is_not_a_note(journal_dir):
    _write("old")
    page = journal_dir / "technical" / "reference.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# Reference\n\nA hand-written page, no frontmatter.\n")

    with pytest.raises(ValueError) as excinfo:
        supersede_journal_note(
            category="technical",
            slug="old",
            reason="stale",
            superseded_by="technical/reference",
        )

    message = str(excinfo.value)
    assert "[SYSTEM SUGGESTION]" in message
    assert "page rather than a note" in message
    assert "superseded_by" not in (journal_dir / "technical" / "old.md").read_text()
