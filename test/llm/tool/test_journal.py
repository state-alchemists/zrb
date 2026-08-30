import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.tool.journal import search_journal


@pytest.fixture
def journal_dir(tmp_path):
    d = tmp_path / "journal"
    d.mkdir()
    return str(d)


@pytest.fixture
def journal_with_entries(journal_dir):
    with open(os.path.join(journal_dir, "2024-01-01.md"), "w") as f:
        f.write("Today I fixed a bug in the auth module.\nAll tests passed.\n")
    with open(os.path.join(journal_dir, "2024-01-02.md"), "w") as f:
        f.write("Refactored the database layer.\nImproved query performance.\n")
    return journal_dir


def test_no_journal_dir_configured():
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = ""
        result = search_journal("anything")
    assert "error" in result
    assert "not configured" in result["error"]
    assert "[SYSTEM SUGGESTION]" in result["error"]


def test_journal_dir_missing_is_empty_not_an_error(tmp_path):
    """A journal nobody has written to yet reads as empty, and gets created.

    Reporting it as an error made the whole memory layer look unavailable, so
    the model fell back to "I cannot journal" instead of writing its first note.
    """
    missing = tmp_path / "never-written" / "journal"
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(missing)
        result = search_journal("anything")
    assert "error" not in result
    assert result["results"] == []
    assert missing.is_dir()


def test_journal_dir_uncreatable_reports_error(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(blocker / "journal")
        result = search_journal("anything")
    assert "error" in result
    assert "Cannot create journal directory" in result["error"]


def test_invalid_regex(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        result = search_journal("[invalid")
    assert "error" in result
    assert "Invalid regex" in result["error"]


def test_no_matches(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("xyzzy_no_match")
    assert result["summary"] == "No matches found."
    assert result["results"] == []


def test_find_matches_python_fallback(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("auth")
    assert "results" in result
    assert len(result["results"]) > 0
    files = [r["file"] for r in result["results"]]
    assert any("2024-01-01" in f for f in files)


def test_case_insensitive_by_default(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("AUTH")
    assert len(result["results"]) > 0


def test_case_sensitive_no_match(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("AUTH", case_sensitive=True)
    assert result["results"] == []


def test_result_structure(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("tests")
    assert "summary" in result
    assert "results" in result
    for entry in result["results"]:
        assert "file" in entry
        assert "line" in entry
        assert "content" in entry


def test_find_matches_with_ripgrep(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value="/usr/bin/rg"):
            result = search_journal("database")
    assert "results" in result
    # rg path returns something (may return no matches if rg not installed, just no error)
    assert "error" not in result


def test_rg_subprocess_timeout_returns_error(journal_with_entries):
    """If rg times out, the helper surfaces an error instead of crashing."""
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with (
            patch("zrb.llm.tool.journal.shutil.which", return_value="/usr/bin/rg"),
            patch(
                "zrb.llm.tool.journal.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="rg", timeout=30),
            ),
        ):
            result = search_journal("database")
    assert "error" in result
    assert "rg failed" in result["error"]


def test_rg_returncode_2_surfaces_stderr(journal_with_entries):
    """rg's exit code 2 signals an internal error; stderr should be passed through."""
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        completed = MagicMock()
        completed.returncode = 2
        completed.stderr = "regex parse failure"
        completed.stdout = ""
        with (
            patch("zrb.llm.tool.journal.shutil.which", return_value="/usr/bin/rg"),
            patch("zrb.llm.tool.journal.subprocess.run", return_value=completed),
        ):
            result = search_journal("database")
    assert "error" in result
    assert "regex parse failure" in result["error"]


def test_python_search_skips_hidden_files(journal_dir):
    """Files prefixed with `.` are excluded from the python fallback walk."""
    with open(os.path.join(journal_dir, "visible.md"), "w") as f:
        f.write("findme here\n")
    with open(os.path.join(journal_dir, ".hidden.md"), "w") as f:
        f.write("findme also\n")
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_dir
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("findme")
    files = {r["file"] for r in result["results"]}
    assert "visible.md" in files
    assert ".hidden.md" not in files


def test_zero_hit_suggests_similar_note_titles(tmp_path):
    journal_dir = tmp_path / "journal"
    (journal_dir / "technical").mkdir(parents=True)
    (journal_dir / "technical" / "retry-policy.md").write_text(
        "# Retry policy is not concurrency-safe\n\nsome body\n", encoding="utf-8"
    )
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(journal_dir)
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("Retry policy is not concurrency safe")
    assert result["results"] == []
    assert "did_you_mean" in result
    assert any("Retry policy" in s for s in result["did_you_mean"])


def test_zero_hit_with_no_close_titles_omits_did_you_mean(journal_with_entries):
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_with_entries
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("xyzzy_no_match")
    assert result["results"] == []
    assert "did_you_mean" not in result


def test_python_search_swallows_file_open_errors(journal_dir):
    """A file that fails to open is skipped silently — search continues."""
    with open(os.path.join(journal_dir, "good.md"), "w") as f:
        f.write("findme here\n")

    real_open = open

    def fake_open(path, *args, **kwargs):
        if "good.md" in str(path):
            raise PermissionError("denied")
        return real_open(path, *args, **kwargs)

    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_dir
        with (
            patch("zrb.llm.tool.journal.shutil.which", return_value=None),
            patch("builtins.open", side_effect=fake_open),
        ):
            result = search_journal("findme")
    # No crash; just no matches
    assert result.get("results") == []


# --- Writers -------------------------------------------------------------
#
# The four journal invariants (broken-link, missing-backlink, orphan,
# missing-index) are held by the writers by construction rather than checked
# after the fact, so these tests assert the construction.


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


def test_writers_refuse_when_the_journal_dir_is_unset():
    from zrb.llm.tool.journal_write import log_activity

    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = ""
        with pytest.raises(ValueError) as excinfo:
            log_activity("anything")
    assert "not configured" in str(excinfo.value)


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
