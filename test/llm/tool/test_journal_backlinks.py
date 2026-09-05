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


def test_rewriting_a_note_keeps_the_backlinks_other_notes_added(writable_journal):
    """The missing-backlink invariant, broken by this module's own writer.

    A note is re-written whenever its finding is refined, and the whole file is
    composed from the arguments — so a plain truncate dropped the `## Backlinks`
    entries that *other* notes had inserted. Linking second→first and then
    updating `first` left `first` with no way back, while `second` kept its
    forward link: exactly the half-edge the deleted `journal-lint.py` used to
    catch.
    """
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
        category="projects",
        slug="second",
        title="Second",
        context="c",
        finding="f",
        source="s",
        links=["technical/first.md"],
    )
    assert "[Second]" in _read(writable_journal, "technical", "first.md")

    write_journal_note(
        category="technical",
        slug="first",
        title="First",
        context="revised",
        finding="revised finding",
        source="s:2",
    )

    first = _read(writable_journal, "technical", "first.md")
    assert "revised finding" in first
    assert "[Second]" in first, "the backlink another note wrote was dropped"
    assert "- [index](index.md)" in first
    assert first.count("[Second]") == 1


def test_rewriting_a_note_keeps_its_own_forward_links(writable_journal):
    """The same half-edge from the other end.

    Dropping `## Related` while the target keeps its backlink leaves a backlink
    pointing at a note that no longer claims the relationship.
    """
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
        category="projects",
        slug="second",
        title="Second",
        context="c",
        finding="f",
        source="s",
        links=["technical/first.md"],
    )

    write_journal_note(
        category="projects",
        slug="second",
        title="Second",
        context="revised",
        finding="revised",
        source="s:2",
    )

    second = _read(writable_journal, "projects", "second.md")
    assert "## Related" in second
    assert "[First]" in second
    assert second.count("[First]") == 1


def test_hud_section_evicts_oldest_past_the_cap(writable_journal):
    from zrb.llm.tool import journal_write
    from zrb.llm.tool.journal_write import write_journal_note

    journal_write.CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 2
    for i in range(3):
        write_journal_note(
            category="user",
            slug=f"pref-{i}",
            title="T",
            context="c",
            finding="f",
            source="s",
            hud_line=f"Preference number {i}.",
        )

    index = _read(writable_journal, "index.md")
    user_section = index.split("## User", 1)[1].split("\n## ", 1)[0]
    assert "Preference number 0." not in user_section
    assert "Preference number 1." in user_section
    assert "Preference number 2." in user_section


def test_revision_appends_a_dated_history_entry(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="technical",
        slug="retry-policy",
        title="Retry policy is not concurrency-safe",
        context="Any concurrent task run",
        finding="`retry_period` is read without a lock",
        source="base_task.py:160",
    )
    write_journal_note(
        category="technical",
        slug="retry-policy",
        title="Retry policy is not concurrency-safe",
        context="Any concurrent task run",
        finding="Actually it IS lock-protected as of the refactor",
        source="base_task.py:200",
    )

    note = _read(writable_journal, "technical", "retry-policy.md")
    assert "## History" in note
    assert "`retry_period` is read without a lock" in note
    assert "Actually it IS lock-protected as of the refactor" in note
    assert note.index("## History") < note.index("## Backlinks")


def test_history_is_capped_at_three_entries(writable_journal):
    from zrb.llm.tool.journal_write import write_journal_note

    for i in range(5):
        write_journal_note(
            category="technical",
            slug="evolving",
            title="Evolving note",
            context="c",
            finding=f"finding version {i}",
            source="s",
        )

    note = _read(writable_journal, "technical", "evolving.md")
    history = note.split("## History", 1)[1].split("\n## ", 1)[0]
    assert "finding version 0" not in history
    assert "finding version 1" in history
    assert "finding version 2" in history
    assert "finding version 3" in history
    # version 4 is the current finding, not a history entry.
    assert "**Finding:** finding version 4" in note


def test_delete_journal_note_removes_the_file_and_every_reference(writable_journal):
    from zrb.llm.tool.journal_write import delete_journal_note, write_journal_note

    write_journal_note(
        category="technical",
        slug="first",
        title="First",
        context="c",
        finding="f",
        source="s",
    )
    write_journal_note(
        category="projects",
        slug="second",
        title="Second",
        context="c",
        finding="f",
        source="s",
        links=["technical/first.md"],
    )

    result = delete_journal_note("technical", "first")

    assert "Deleted" in result
    assert not os.path.isfile(os.path.join(writable_journal, "technical", "first.md"))
    # Scrubbed from the category index, the root's Recent Insights...
    assert "first.md" not in _read(writable_journal, "technical", "index.md")
    assert "technical/first.md" not in _read(writable_journal, "index.md")
    # ...and from the other note's forward link to it.
    assert "[First]" not in _read(writable_journal, "projects", "second.md")


def test_delete_journal_note_rejects_a_missing_slug(writable_journal):
    from zrb.llm.tool.journal_write import delete_journal_note, write_journal_note

    write_journal_note(
        category="technical",
        slug="exists",
        title="T",
        context="c",
        finding="f",
        source="s",
    )
    with pytest.raises(ValueError) as excinfo:
        delete_journal_note("technical", "does-not-exist")
    assert "SYSTEM SUGGESTION" in str(excinfo.value)


def test_delete_journal_note_rejects_an_unknown_category(writable_journal):
    from zrb.llm.tool.journal_write import delete_journal_note

    with pytest.raises(ValueError) as excinfo:
        delete_journal_note("../escape", "x")
    assert "unknown category" in str(excinfo.value)


def test_write_journal_note_holds_an_exclusive_lock_for_the_whole_call(
    writable_journal,
):
    """The coarse-grained lock is actually engaged around the write, not just
    present in the module — verified via the real `fcntl` calls rather than
    by trying to provoke an actual race (inherently flaky in a unit test)."""
    import fcntl

    from zrb.llm.tool.journal_write import write_journal_note

    calls: list[tuple[int, ...]] = []
    real_flock = fcntl.flock

    def recording_flock(fd, operation):
        calls.append((operation,))
        return real_flock(fd, operation)

    with patch("zrb.llm.tool.journal_write.fcntl.flock", side_effect=recording_flock):
        write_journal_note(
            category="technical",
            slug="locked",
            title="T",
            context="c",
            finding="f",
            source="s",
        )

    assert calls == [(fcntl.LOCK_EX,), (fcntl.LOCK_UN,)]
    assert os.path.isfile(os.path.join(writable_journal, ".lock"))


def test_log_activity_holds_the_same_lock(writable_journal):
    import fcntl

    from zrb.llm.tool.journal_write import log_activity

    calls: list[tuple[int, ...]] = []
    real_flock = fcntl.flock

    def recording_flock(fd, operation):
        calls.append((operation,))
        return real_flock(fd, operation)

    with patch("zrb.llm.tool.journal_write.fcntl.flock", side_effect=recording_flock):
        log_activity("did a thing")

    assert calls == [(fcntl.LOCK_EX,), (fcntl.LOCK_UN,)]
