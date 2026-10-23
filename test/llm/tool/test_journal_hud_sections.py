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
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
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


@pytest.mark.parametrize("index_name", ["../escape.md", "nested/index.md", ""])
def test_configured_index_name_must_be_a_filename(writable_journal, index_name):
    from zrb.llm.tool.journal_write import ensure_journal_tree

    with patch("zrb.llm.tool.journal_write.CFG.LLM_JOURNAL_INDEX_FILE", index_name):
        with pytest.raises(ValueError, match="LLM_JOURNAL_INDEX_FILE"):
            ensure_journal_tree()


def test_an_absolute_index_name_is_rejected(tmp_path, writable_journal):
    from zrb.llm.tool.journal_write import ensure_journal_tree

    index_name = str(tmp_path / "escape.md")
    with patch("zrb.llm.tool.journal_write.CFG.LLM_JOURNAL_INDEX_FILE", index_name):
        with pytest.raises(ValueError, match="LLM_JOURNAL_INDEX_FILE"):
            ensure_journal_tree()
    assert not (tmp_path / "escape.md").exists()


def test_a_busy_journal_returns_an_actionable_error(writable_journal):
    """The message has to say a lock held the write, for how long, and which
    setting raises the wait — an agent that only reads "busy" retries blindly."""
    from zrb.llm.tool.journal_write import log_activity
    from zrb.util.file_lock import FileLockTimeout

    with patch(
        "zrb.llm.tool.journal_write.hold_file_lock",
        side_effect=FileLockTimeout("lock held"),
    ):
        with pytest.raises(ValueError) as raised:
            log_activity("checked lock behavior")

    message = str(raised.value)
    assert "[SYSTEM SUGGESTION]" in message
    assert "busy" in message
    assert "another writer held" in message
    assert "LLM_JOURNAL_LOCK_TIMEOUT" in message
    assert "wrote nothing" in message


def test_a_journal_write_passes_its_configured_lock_timeout(writable_journal):
    from zrb.llm.tool.journal_write import log_activity
    from zrb.util.file_lock import hold_file_lock

    with patch(
        "zrb.llm.tool.journal_write.hold_file_lock", wraps=hold_file_lock
    ) as lock:
        log_activity("checked lock timeout")

    assert lock.call_args.kwargs["timeout"] == 0.1


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


def test_a_migrated_index_keeps_a_directory_link_it_does_not_own(writable_journal):
    """A hand-written label and a link to something outside the journal are the
    user's, not the migration's: only the missing category links are added."""
    from zrb.llm.tool.journal_write import log_activity

    _write(
        writable_journal,
        "# Journal\n\n"
        "## Directories\n\n"
        "- [My notes](user/index.md) · [external](other/index.md)\n\n"
        "## Recent Insights\n\n",
    )

    log_activity("wrote a note")

    directories = [
        line
        for line in _read(writable_journal, "index.md").splitlines()
        if line.startswith("- [")
    ][0]
    assert "[My notes](user/index.md)" in directories
    assert "[external](other/index.md)" in directories
    assert "[agent](agent/index.md)" in directories
    for category in ("preferences", "projects", "technical", "activity-log"):
        assert f"[{category}]({category}/index.md)" in directories
    # Added, not reordered: the two the journal already had stay in front.
    assert directories.index("[My notes]") < directories.index("[agent]")


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


def test_hud_line_preserves_a_link_to_a_different_note(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="technical",
        slug="main",
        title="Main",
        context="c",
        finding="f",
        source="s",
        hud_line="See also ([note](technical/other.md))",
    )

    index = _read(writable_journal, "index.md")
    assert "See also ([note](technical/other.md)) ([note](technical/main.md))" in index


def test_repeating_a_pinned_line_with_its_link_does_not_pin_it_twice(
    writable_journal,
):
    """The tool's own output is in the model's context, so a revision can hand
    the line back verbatim, `([note](…))` included. Appending a second link to
    that pinned the same note twice on one line."""
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="technical",
        slug="retry-policy",
        title="Retry policy",
        context="writing a retry",
        finding="not concurrency-safe",
        source="src/retry.py:12",
        hud_line="Retry is not concurrency-safe.",
    )
    write_journal_note(
        category="technical",
        slug="retry-policy",
        title="Retry policy",
        context="writing a retry",
        finding="not concurrency-safe",
        source="src/retry.py:12",
        hud_line="- Retry is not concurrency-safe. ([note](technical/retry-policy.md))",
    )

    pinned = [
        line
        for line in _read(writable_journal, "index.md").splitlines()
        if "Retry is not" in line
    ]
    assert pinned == [
        "- Retry is not concurrency-safe. ([note](technical/retry-policy.md))"
    ]


def test_a_line_an_earlier_version_pinned_twice_is_written_once(writable_journal):
    """A journal written before the fix carries a doubled link; the next write of
    that note replaces the line rather than leaving the duplicate in place."""
    from zrb.llm.tool.journal_write import write_journal_note

    _write(
        writable_journal,
        "# Journal\n\n"
        "## Active Constraints\n\n"
        "- Retry is not concurrency-safe. ([note](technical/retry-policy.md)) "
        "([note](technical/retry-policy.md))\n\n"
        "## Directories\n\n- [technical](technical/index.md)\n\n"
        "## Recent Insights\n\n",
    )

    write_journal_note(
        category="technical",
        slug="retry-policy",
        title="Retry policy",
        context="writing a retry",
        finding="not concurrency-safe",
        source="src/retry.py:12",
        hud_line="Retry is not concurrency-safe.",
    )

    pinned = _read(writable_journal, "index.md")
    assert pinned.count("([note](technical/retry-policy.md))") == 1
