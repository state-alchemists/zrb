import os
from unittest.mock import patch

import pytest


@pytest.fixture
def writable_journal(tmp_path):
    """Patch CFG for the writer module and return the journal root."""
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        # A real int, matching the shipped default — tests that care about
        # eviction override this explicitly to a small cap.
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        # Off here so this file's tests stay fast and independent of a `git`
        # binary being present — test_journal_git.py exercises git-backing.
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        yield str(root)


def _read(*parts) -> str:
    with open(os.path.join(*parts), "r", encoding="utf-8") as f:
        return f.read()


def test_log_activity_builds_the_whole_tree_on_a_cold_journal(writable_journal):
    from zrb.llm.tool.journal_write import log_activity

    result = log_activity("fixed the retry bug", files=["src/retry.py"])

    assert "Logged to" in result
    # missing-index: every level down to the day file has one.
    root_index = _read(writable_journal, "index.md")
    assert "## Directories" in root_index
    for name in ("user", "preferences", "projects", "technical", "activity-log"):
        # orphan: each directory is reachable from the root index.
        assert f"{name}/index.md" in root_index
        assert os.path.isfile(os.path.join(writable_journal, name, "index.md"))

    day_path = os.path.join(writable_journal, result.split("Logged to ")[1])
    assert os.path.isfile(day_path)
    day = _read(day_path)
    assert "fixed the retry bug" in day
    assert "Files: src/retry.py" in day
    assert "## Backlinks" in day


def test_log_activity_appends_rather_than_rewrites(writable_journal):
    from zrb.llm.tool.journal_write import log_activity

    first = log_activity("ran the suite")
    second = log_activity("bumped the version", files=["pyproject.toml"])
    assert first == second  # same day file

    day = _read(writable_journal, second.split("Logged to ")[1])
    assert "ran the suite" in day
    assert "bumped the version" in day
    # Backlinks stay last so the block does not drift into the entry list.
    assert day.index("bumped the version") < day.index("## Backlinks")


def test_log_activity_omits_missing_files_as_a_dash(writable_journal):
    from zrb.llm.tool.journal_write import log_activity

    result = log_activity("answered a question")
    assert "Files: —." in _read(writable_journal, result.split("Logged to ")[1])


def test_write_journal_note_registers_itself_everywhere(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="technical",
        slug="retry-policy",
        title="Retry policy is not concurrency-safe",
        context="Any concurrent task run",
        finding="`retry_period` is read without a lock",
        source="base_task.py:160",
    )

    note = _read(writable_journal, "technical", "retry-policy.md")
    assert note.startswith("---\nslug: retry-policy\n---")
    assert "**Finding:** `retry_period` is read without a lock" in note
    assert "## Backlinks" in note
    # orphan: reachable from the category index and from the root's HUD list.
    assert "retry-policy.md" in _read(writable_journal, "technical", "index.md")
    root_index = _read(writable_journal, "index.md")
    assert "## Recent Insights" in root_index
    assert "technical/retry-policy.md" in root_index


def test_write_journal_note_inserts_reciprocal_backlinks(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="technical",
        slug="first",
        title="First",
        context="c",
        finding="f",
        source="s",
    )
    write_journal_note(
        category="technical",
        slug="second",
        title="Second",
        context="c",
        finding="f",
        source="s",
        links=["technical/first.md"],
    )

    # missing-backlink: the target gained an entry pointing back.
    first = _read(writable_journal, "technical", "first.md")
    assert "[Second](second.md)" in first
    assert first.index("## Backlinks") < first.index("[Second](second.md)")
    # broken-link: the forward link resolves.
    second = _read(writable_journal, "technical", "second.md")
    assert "[First](first.md)" in second


def test_write_journal_note_rejects_a_link_that_does_not_exist(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="technical",
            slug="orphaned",
            title="T",
            context="c",
            finding="f",
            source="s",
            links=["technical/nope.md"],
        )
    assert "SYSTEM SUGGESTION" in str(excinfo.value)
    assert "does not exist" in str(excinfo.value)


def test_write_journal_note_rejects_a_link_outside_the_journal(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="technical",
            slug="escapee",
            title="T",
            context="c",
            finding="f",
            source="s",
            links=["../../etc/passwd"],
        )
    assert "outside the journal" in str(excinfo.value)


@pytest.mark.parametrize("bad", ["Not Kebab", "trailing-", "under_score", ""])
def test_write_journal_note_rejects_a_bad_slug(writable_journal, bad):
    from zrb.llm.tool.journal_write import write_journal_note

    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="user",
            slug=bad,
            title="T",
            context="c",
            finding="f",
            source="s",
        )
    assert "kebab-case" in str(excinfo.value)


def test_write_journal_note_rejects_an_unknown_category(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="../escape",
            slug="x",
            title="T",
            context="c",
            finding="f",
            source="s",
        )
    assert "unknown category" in str(excinfo.value)


def test_hud_line_lands_in_the_section_matching_the_category(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="preferences",
        slug="terse-replies",
        title="Prefers terse replies",
        context="Every turn",
        finding="No preamble, no summary of what was just said",
        source="stated 2026-08-04",
        hud_line="Prefers terse replies, no preamble.",
    )

    index = _read(writable_journal, "index.md")
    preferences = index.split("## Preferences", 1)[1].split("\n## ", 1)[0]
    assert "Prefers terse replies, no preamble." in preferences
    # The unbounded section must stay last so overflow only evicts itself.
    assert index.index("## Recent Insights") > index.index("## Directories")


def test_hud_line_does_not_duplicate_on_a_repeat(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    for slug in ("first-say", "second-say"):
        write_journal_note(
            category="user",
            slug=slug,
            title="T",
            context="c",
            finding="f",
            source="s",
            hud_line="Goes by Go.",
        )

    assert _read(writable_journal, "index.md").count("Goes by Go.") == 1


def test_revised_hud_line_replaces_the_notes_earlier_line(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    for score in ("7.8", "8.2"):
        write_journal_note(
            category="technical",
            slug="prompt-review",
            title="Prompt review",
            context="c",
            finding="f",
            source="s",
            hud_line=f"Prompt scored {score}/10.",
        )

    index = _read(writable_journal, "index.md")
    assert "Prompt scored 7.8/10." not in index
    assert "Prompt scored 8.2/10. ([note](technical/prompt-review.md))" in index


def test_retitled_note_is_relabelled_not_duplicated_in_indexes(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    for title in ("Aug review", "Sep review"):
        write_journal_note(
            category="technical",
            slug="prompt-review",
            title=title,
            context="c",
            finding="f",
            source="s",
        )

    for index_path in ("index.md", "technical/index.md"):
        index = _read(writable_journal, index_path)
        assert index.count("prompt-review.md)") == 1
        assert "[Sep review]" in index


def test_revision_collapses_preexisting_duplicate_index_entries(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="technical",
        slug="review",
        title="Old",
        context="c",
        finding="f",
        source="s",
    )
    # A journal written before relabelling existed: two lines, one target.
    index_path = os.path.join(writable_journal, "technical", "index.md")
    with open(index_path, "a", encoding="utf-8") as f:
        f.write("- [Older](review.md)\n")

    write_journal_note(
        category="technical",
        slug="review",
        title="Old",
        context="c",
        finding="f2",
        source="s",
    )

    index = _read(writable_journal, "technical", "index.md")
    assert index.count("review.md)") == 1
    assert "- [Old](review.md)" in index


def test_writers_refuse_when_the_journal_dir_is_unset():
    from zrb.llm.tool.journal_write import log_activity

    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = ""
        with pytest.raises(ValueError) as excinfo:
            log_activity("anything")
    assert "not configured" in str(excinfo.value)
