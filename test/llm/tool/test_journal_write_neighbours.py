"""What a note write says about the notes it sits beside.

The write is the one moment a contradiction is known to exist: the writer has the
new fact in hand and the index in front of it. These tests pin the line that puts
the note being contradicted in front of it too, and pin that a write about an
unrelated subject stays quiet.
"""

import pytest


@pytest.fixture
def writable_journal(tmp_path):
    """Patch CFG for the writer module and return the journal root."""
    from unittest.mock import patch

    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 25
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        yield str(root)


def _write(title: str, slug: str, keywords: list[str]) -> str:
    from zrb.llm.tool.journal_write import write_journal_note

    return write_journal_note(
        category="technical",
        slug=slug,
        title=title,
        context="while testing the neighbour hint",
        finding="A finding that stands on its own, with the evidence beside it.",
        source="test/llm/tool/test_journal_write_neighbours.py",
        hud_line=title,
        applies_when="while this test runs",
        keywords=keywords,
    )


def test_a_write_names_the_note_it_sits_beside(writable_journal):
    """The failure this exists for: advice in one note, its correction in another,
    and nothing ever putting the two in front of the same reader."""
    _write(
        "Windows CI red at Install dependencies",
        "windows-ci",
        ["windows", "ci", "poetry", "cache"],
    )

    result = _write(
        "Windows CI needs its poetry cache cleared",
        "windows-cache",
        ["windows", "ci", "poetry", "cache"],
    )

    assert "Nearby:" in result
    assert "technical/windows-ci.md" in result
    assert '"Windows CI red at Install dependencies"' in result
    assert "revise it now" in result


def test_a_write_about_something_else_names_nothing(writable_journal):
    """A hint that fires on every write is read as boilerplate and stops being
    read at all."""
    _write(
        "Windows CI red at Install dependencies",
        "windows-ci",
        ["windows", "ci", "poetry", "cache"],
    )

    result = _write(
        "Speech reads a reply a sentence at a time",
        "speech-stream",
        ["speech", "tts", "streaming"],
    )

    assert "Nearby:" not in result
