"""A journal written before the indexes were derived keeps what it held.

Its pins and HUD lines lived only in the text of `index.md`. The first journal
call reads them into the notes they link, wherever a line can be matched to a
note, and leaves every other line where it was.
"""

import os
from unittest.mock import patch

import pytest

from zrb.llm.tool.journal_write import (
    ensure_journal_tree,
    log_activity,
    supersede_journal_note,
    write_journal_note,
)

_OLD_NOTE = (
    "---\nslug: {slug}\napplies_when: not stated\nstatus: active\n---\n"
    "# {title}\n\n**Context:** c\n**Finding:** f\n**Source:** s\n\n"
    "## Backlinks\n\n- [index](index.md)\n"
)

_OLD_INDEX = """# Journal

## User

- Goes by Go. ([note](user/identity.md))
- Hand-added reminder.
- Prefers terse replies. ([note](preferences/terse.md))

## Constraints

- 📌 Tests stay public-API only. ([note](technical/tests-public.md))

## Agent

## Recent

- Retry is capped. ([note](technical/retry.md)) ([note](technical/retry.md))
- Points at a note that is gone. ([note](technical/missing.md))

## Directories

- [user](user/index.md) · [agent](agent/index.md) · [preferences](preferences/index.md) · [projects](projects/index.md) · [technical](technical/index.md) · [activity-log](activity-log/index.md)

## Recent Insights

- [Identity](user/identity.md)
- [Retry](technical/retry.md)
"""


@pytest.fixture
def old_journal(tmp_path):
    """A journal in the format that kept pins in the index text only."""
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 25
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        ensure_journal_tree()
        for category, slug in (
            ("user", "identity"),
            ("preferences", "terse"),
            ("technical", "tests-public"),
            ("technical", "retry"),
        ):
            _write(
                str(root),
                f"{category}/{slug}.md",
                _OLD_NOTE.format(slug=slug, title=slug.title()),
            )
        _write(str(root), "index.md", _OLD_INDEX)
        yield str(root)


def _read(root: str, relative: str = "index.md") -> str:
    with open(os.path.join(root, relative), "r", encoding="utf-8") as f:
        return f.read()


def _write(root: str, relative: str, text: str) -> None:
    with open(os.path.join(root, relative), "w", encoding="utf-8") as f:
        f.write(text)


def _section(root: str, name: str) -> list[str]:
    body = _read(root).split(f"## {name}\n", 1)[1].split("\n## ", 1)[0]
    return [line for line in body.splitlines() if line.strip()]


def test_pins_and_lines_move_into_the_notes_they_link(old_journal):
    log_activity("first call")

    tests_note = _read(old_journal, "technical/tests-public.md")
    assert "hud_line: Tests stay public-API only." in tests_note
    assert "pinned: true" in tests_note
    identity = _read(old_journal, "user/identity.md")
    assert "hud_line: Goes by Go." in identity
    assert "pinned" not in identity
    assert "updated: " in identity
    # A doubled own link, which an earlier version could write, is read once.
    assert "hud_line: Retry is capped.\n" in _read(old_journal, "technical/retry.md")


def test_the_index_is_rendered_with_every_line_kept_in_place(old_journal):
    log_activity("first call")

    # The old index listed oldest first; the render lists newest first, so the
    # two owned lines swap while the hand-written one keeps its place between.
    assert _section(old_journal, "User") == [
        "- Prefers terse replies. ([note](preferences/terse.md))",
        "- Hand-added reminder.",
        "- Goes by Go. ([note](user/identity.md))",
    ]
    assert _section(old_journal, "Constraints") == [
        "- 📌 Tests stay public-API only. ([note](technical/tests-public.md))"
    ]
    # The doubled line is collapsed to one; the line for a note that is gone has
    # no note to account for it, so it stays, after it.
    assert _section(old_journal, "Recent") == [
        "- Retry is capped. ([note](technical/retry.md))",
        "- Points at a note that is gone. ([note](technical/missing.md))",
    ]
    assert "- [Identity](user/identity.md)" in _read(old_journal)
    assert "- [Tests-Public](tests-public.md)" in _read(
        old_journal, "technical/index.md"
    )


def test_migration_is_idempotent(old_journal):
    log_activity("first call")
    index = _read(old_journal)
    notes = {
        path: _read(old_journal, path)
        for path in ("user/identity.md", "technical/tests-public.md")
    }

    log_activity("second call")

    assert _read(old_journal) == index
    for path, text in notes.items():
        assert _read(old_journal, path) == text


def test_the_order_of_a_section_survives_the_move(old_journal):
    log_activity("first call")

    write_journal_note("user", "new", "New", "c", "f", "s", hud_line="Newest.")

    user = _section(old_journal, "User")
    assert user.index("- Prefers terse replies. ([note](preferences/terse.md))") < (
        user.index("- Goes by Go. ([note](user/identity.md))")
    )
    assert user[0] == "- Newest. ([note](user/new.md))"


def test_a_migrated_note_can_be_superseded(old_journal):
    result = supersede_journal_note("technical", "tests-public", "no longer true")

    assert "tests-public" not in _read(old_journal)
    assert "Removed from the index: - 📌 Tests stay public-API only." in result
    assert "- [Tests-Public](tests-public.md)" in _read(
        old_journal, "technical/index.md"
    )
