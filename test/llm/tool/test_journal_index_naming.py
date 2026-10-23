"""One knob names every index, for the writers and the reader alike.

`render_journal_index` resolves the root index from `LLM_JOURNAL_INDEX_FILE`, so
a writer that hardcoded `index.md` wrote an index no session ever injected. These
tests drive the writers at every level — root, category, note backlink, activity
day — and check that each name follows the setting.
"""

from unittest.mock import patch


def _write_with_index_name(root, index_name: str) -> None:
    """Drive both writers against a journal whose indexes carry *index_name*."""
    from zrb.llm.tool.journal_write import log_activity, write_journal_note

    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = index_name
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        write_journal_note(
            "technical",
            "retry-policy",
            "Retry policy",
            "c",
            "f",
            "s",
            hud_line="Retry is not concurrency-safe.",
        )
        log_activity("logged a line")


def test_every_index_is_named_by_the_configured_index_file(tmp_path):
    """`render_journal_index` resolves the root index from this knob, so a writer
    that hardcoded `index.md` wrote an index no session ever injected."""
    root = tmp_path / "notes"

    _write_with_index_name(root, "notes-index.md")

    assert (root / "notes-index.md").is_file()
    assert not (root / "index.md").exists()
    for name in ("user", "agent", "preferences", "projects", "technical"):
        assert (root / name / "notes-index.md").is_file()
        assert not (root / name / "index.md").exists()
    root_index = (root / "notes-index.md").read_text(encoding="utf-8")
    assert "[technical](technical/notes-index.md)" in root_index
    assert "Retry is not concurrency-safe." in root_index
    note = (root / "technical" / "retry-policy.md").read_text(encoding="utf-8")
    assert "- [index](notes-index.md)" in note
    # The deepest level: the activity day file links its month index by name.
    # The month index sits in the same directory and matches the same glob, so
    # the day file is picked by name rather than by whatever order the
    # filesystem returns.
    day_file = next(
        path
        for path in (root / "activity-log").glob("*/*/*.md")
        if path.name != "notes-index.md"
    )
    day_content = day_file.read_text(encoding="utf-8")
    assert "- [month index](notes-index.md)" in day_content


def test_a_changed_index_name_starts_fresh_indexes_and_keeps_the_old_one(tmp_path):
    """As `LLM_JOURNAL_INDEX_FILE`'s doc says: nothing is renamed, so an existing
    journal keeps the indexes it already has under their old name."""
    root = tmp_path / "notes"
    root.mkdir()
    old_index = "# Journal\n\n## User\n\n- Goes by Go.\n"
    (root / "index.md").write_text(old_index, encoding="utf-8")

    _write_with_index_name(root, "notes-index.md")

    assert (root / "index.md").read_text(encoding="utf-8") == old_index
    assert "## Directories" in (root / "notes-index.md").read_text(encoding="utf-8")
