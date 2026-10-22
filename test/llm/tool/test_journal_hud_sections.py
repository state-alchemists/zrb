"""The root index's HUD sections: where a note lands, and how an old index gains
the section it predates.

The section headings are load-bearing, and the index is a shared file, so both
the placement and the moment the file is rewritten are behaviour worth pinning.
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
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        yield str(root)


def _read(*parts) -> str:
    with open(os.path.join(*parts), "r", encoding="utf-8") as f:
        return f.read()


def _write(root, text: str) -> None:
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "index.md"), "w", encoding="utf-8") as f:
        f.write(text)


def test_an_agent_note_pins_under_the_agent_section(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="agent",
        slug="avatar-wardrobe",
        title="Avatar: tactical is my pick",
        context="Choosing what I wear in zrb's face window",
        finding="tara-tactical for a working day, tara-kimono for quiet evenings",
        source="FaceLook, 2026-10-22",
        hud_line="Avatar: tactical is my standing pick.",
    )

    index = _read(writable_journal, "index.md")
    agent = index.split("## Agent", 1)[1].split("\n## ", 1)[0]
    preferences = index.split("## Preferences", 1)[1].split("\n## ", 1)[0]
    assert "Avatar: tactical is my standing pick." in agent
    assert "([note](agent/avatar-wardrobe.md))" in agent
    assert "Avatar" not in preferences
    # Durable sections stay ahead of the capped tail.
    assert index.index("## Agent") < index.index("## Active Constraints")


def test_creating_the_tree_leaves_an_existing_index_alone(writable_journal):
    """The migration is a read-modify-write, so it waits for the journal lock.

    Rewriting the index here, before `hold_file_lock`, could write back a copy
    read before another writer added a line — a lost update on both sides of a
    call that succeeded.
    """
    from zrb.llm.tool.journal_write import ensure_journal_tree

    old_index = "# Journal\n\n## User\n\n- Goes by Go.\n"
    _write(writable_journal, old_index)

    ensure_journal_tree()

    assert _read(writable_journal, "index.md") == old_index


def test_an_index_written_before_the_agent_section_gains_it_in_place(
    writable_journal,
):
    """A journal created earlier keeps its skeleton; the new section goes where
    it belongs rather than after the unbounded one, where the cap would evict
    it first."""
    from zrb.llm.tool.journal_write import log_activity

    _write(
        writable_journal,
        "# Journal\n\n"
        "## User\n\n- Goes by Go.\n\n"
        "## Preferences\n\n- Prefers terse replies.\n\n"
        "## Active Constraints\n\n- Tests stay public-API only.\n\n"
        "## Directories\n\n- [user](user/index.md)\n\n"
        "## Recent Insights\n\n- [A note](technical/a-note.md)\n",
    )

    log_activity("wrote a note")

    index = _read(writable_journal, "index.md")
    assert "## Agent" in index
    assert index.index("## Preferences") < index.index("## Agent")
    assert index.index("## Agent") < index.index("## Active Constraints")
    assert index.index("## Active Constraints") < index.index("## Recent Insights")
    # Nothing that was already in the index is lost or rewritten.
    for kept in (
        "- Goes by Go.",
        "- Prefers terse replies.",
        "- Tests stay public-API only.",
        "- [A note](technical/a-note.md)",
    ):
        assert kept in index


def test_a_migrated_index_links_the_new_category_in_directories(writable_journal):
    """A section nobody links to is a section nobody reads: the migration adds
    `agent/index.md` to `## Directories` too, in its place among the others."""
    from zrb.llm.tool.journal_write import log_activity

    _write(
        writable_journal,
        "# Journal\n\n"
        "## User\n\n- Goes by Go.\n\n"
        "## Preferences\n\n- Prefers terse replies.\n\n"
        "## Active Constraints\n\n- Tests stay public-API only.\n\n"
        "## Directories\n\n"
        "- [user](user/index.md) · [preferences](preferences/index.md)\n\n"
        "## Recent Insights\n\n",
    )

    log_activity("wrote a note")

    directories = [
        line
        for line in _read(writable_journal, "index.md").splitlines()
        if line.startswith("- [")
    ][0]
    # Every category, in the order a journal created now writes them.
    assert directories == (
        "- [user](user/index.md) · [agent](agent/index.md) · "
        "[preferences](preferences/index.md) · "
        "[projects](projects/index.md) · [technical](technical/index.md) · "
        "[activity-log](activity-log/index.md)"
    )
