"""Tests for `SearchJournal` (`zrb/llm/tool/journal.py`)."""

import json
import os
import subprocess
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.tool.journal import find_in_journal, search_journal


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


def _rg_match(path, line_number, text):
    return json.dumps(
        {
            "type": "match",
            "data": {
                "path": {"text": path},
                "line_number": line_number,
                "lines": {"text": text + "\n"},
            },
        }
    )


def _search_with_rg_output(journal_dir, query, stdout):
    completed = MagicMock(returncode=0, stdout=stdout)
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_dir
        with (
            patch("zrb.llm.tool.journal.shutil.which", return_value="/usr/bin/rg"),
            patch("zrb.llm.tool.journal.subprocess.run", return_value=completed) as run,
        ):
            result = search_journal(query)
    return result, run


def test_find_matches_with_ripgrep(journal_with_entries):
    """The rg path runs `rg` and parses its output; no binary needs to exist."""
    journal_file = os.path.join(journal_with_entries, "2024-01-02.md")
    stdout = "\n".join(
        [
            json.dumps({"type": "begin", "data": {"path": {"text": journal_file}}}),
            _rg_match(journal_file, 1, "Refactored the database layer."),
            json.dumps({"type": "summary", "data": {}}),
        ]
    )
    result, run = _search_with_rg_output(journal_with_entries, "database", stdout)
    assert run.call_args.args[0][0] == "rg"
    assert result["results"] == [
        {
            "file": "2024-01-02.md",
            "line": "1",
            "content": "Refactored the database layer.",
        }
    ]


def test_rg_match_in_windows_drive_path_is_parsed(journal_with_entries):
    """A drive-letter colon belongs to the path, not the separator."""
    stdout = _rg_match("C:\\notes\\2024-01-02.md", 7, "key: value")
    result, _ = _search_with_rg_output(journal_with_entries, "value", stdout)
    entry = result["results"][0]
    assert entry["line"] == "7"
    assert entry["content"] == "key: value"
    assert entry["file"].endswith("2024-01-02.md")


def test_rg_match_in_filename_with_colon_digits_is_parsed(journal_with_entries):
    path = os.path.join(journal_with_entries, "note:12:archive.md")
    stdout = _rg_match(path, 7, "matching content")
    result, _ = _search_with_rg_output(journal_with_entries, "matching", stdout)
    assert result["results"] == [
        {"file": "note:12:archive.md", "line": "7", "content": "matching content"}
    ]


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
        "# Concurrency is not safe here\n\nsome body\n", encoding="utf-8"
    )
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(journal_dir)
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            # The words are in the file's name, not in its text, which is what
            # makes this a zero hit a suggestion can still answer.
            result = search_journal("retry policy")
    assert result["results"] == []
    assert "did_you_mean" in result
    assert any("Concurrency" in s for s in result["did_you_mean"])


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


def test_zero_hit_survives_a_note_that_is_not_utf8(tmp_path):
    """Decoding a note strictly made the zero-hit suggestion pass raise, so a
    search that found nothing crashed instead of saying so."""
    journal_dir = tmp_path / "journal"
    (journal_dir / "technical").mkdir(parents=True)
    (journal_dir / "technical" / "latin-1-note.md").write_bytes(b"# Caf\xe9 notes\n")
    (journal_dir / "technical" / "retry-policy.md").write_text(
        "# Concurrency is not safe here\n\nbody\n", encoding="utf-8"
    )
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(journal_dir)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            # The words are in the two file names, so both notes are read to
            # build the suggestions — one of them byte by byte.
            result = search_journal("retry policy")
    assert result["results"] == []
    assert any("Concurrency" in title for title in result.get("did_you_mean", []))


def test_zero_hit_does_not_offer_a_category_index_as_a_title(tmp_path):
    """A directory index is a catalog, not a note: its `# Technical` heading is
    nobody's finding. Skipping it by the literal `index.md` missed a journal
    whose index is named by configuration."""
    journal_dir = tmp_path / "journal"
    (journal_dir / "technical").mkdir(parents=True)
    (journal_dir / "technical" / "notes-index.md").write_text(
        "# Technical\n", encoding="utf-8"
    )
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(journal_dir)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "notes-index.md"
        from zrb.llm.tool.journal import _suggest_similar

        suggestions = _suggest_similar("Technical notes", str(journal_dir))
    assert "Technical" not in suggestions


def test_requiring_every_word_would_miss_the_note_a_question_asks_for(tmp_path):
    """A question is prose, and the note that answers it does not repeat its
    words — so the search reads several plain words as any-of and lets the
    ranking supply the precision.

    Requiring every word was measured on eight questions about notes that
    exist: it found 2 of 8, against 8 of 8 for any-of. This pins the difference
    so the AND gate is not quietly reintroduced as a fix.
    """
    journal_dir = tmp_path / "journal"
    (journal_dir / "technical").mkdir(parents=True)
    (journal_dir / "technical" / "both.md").write_text(
        "# Speech goes silent under load\n\nspeech load\n", encoding="utf-8"
    )
    (journal_dir / "technical" / "one.md").write_text(
        "# Speech notes\n\nspeech\n", encoding="utf-8"
    )
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(journal_dir)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("why does speech go silent under load")

    files = []
    for row in result["results"]:
        if row["file"] not in files:
            files.append(row["file"])
    # The partial match is still returned; the fuller one leads.
    assert files == ["technical/both.md", "technical/one.md"]


def test_case_sensitive_ranking_ignores_a_title_that_only_matches_in_lowercase(
    journal_dir,
):
    with open(os.path.join(journal_dir, "a.md"), "w") as f:
        f.write("# speech load\n\nSpeech\n")
    with open(os.path.join(journal_dir, "b.md"), "w") as f:
        f.write("# Unrelated\n\nSpeech and Load\n")
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_dir
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = search_journal("Speech Load", case_sensitive=True)
    assert result["results"][0]["file"] == "b.md"


def _stamp(days_ago):
    """The `updated:` value a note of the given age carries."""
    moment = datetime.now() - timedelta(days=days_ago)
    return moment.isoformat(timespec="microseconds")


def _write_note(journal_dir, rel, heading, body, updated=None, pinned=False):
    """A note at *rel*: its slug, an optional `updated:`/`pinned:`, heading, body."""
    front = [f"slug: {rel.rsplit('/', 1)[-1].removesuffix('.md')}"]
    if pinned:
        front.append("pinned: true")
    if updated is not None:
        front.append(f"updated: {updated}")
    path = os.path.join(journal_dir, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        block = "".join(f"{line}\n" for line in front)
        f.write(f"---\n{block}---\n# {heading}\n\n{body}\n")


def _write_page(journal_dir, rel, text):
    path = os.path.join(journal_dir, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _ranked(journal_dir, query):
    """The files a search returns, in rank order.

    `find_in_journal`, not `search_journal`: the ranking is this module's job,
    while recording a usage event is a separate one that writes to the real
    usage store."""
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_dir
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = find_in_journal(query)
    return list(dict.fromkeys(row["file"] for row in result["results"]))


def test_a_fresher_note_outranks_an_older_one_at_equal_term_hits(tmp_path):
    """A stale note used to tie with an hour-old one: nothing in the ranking was
    a function of time, so the newest finding could sit behind an old one. The
    paths sort against the expected order, so a tie cannot pass by accident."""
    d = str(tmp_path / "journal")
    _write_note(d, "technical/a-stale.md", "Queue depth", "redis", _stamp(120))
    _write_note(d, "technical/z-fresh.md", "Cache keys", "redis", _stamp(0))

    assert _ranked(d, "redis") == ["technical/z-fresh.md", "technical/a-stale.md"]


def test_a_pinned_note_outranks_an_unpinned_one_of_the_same_age(tmp_path):
    """Equal hits and equal age leave the pin as the only thing to rank by, and
    the paths sort against that order."""
    d = str(tmp_path / "journal")
    stamp = _stamp(3)
    _write_note(d, "technical/a-plain.md", "Queue depth", "redis", stamp)
    _write_note(d, "technical/z-pinned.md", "Cache keys", "redis", stamp, pinned=True)

    assert _ranked(d, "redis") == ["technical/z-pinned.md", "technical/a-plain.md"]


def test_a_note_outranks_the_index_and_the_log_however_old_it_is(tmp_path):
    """Age orders the note band. It never lifts a page that mentions everything
    over a note that mentions the one thing that was asked for."""
    d = str(tmp_path / "journal")
    _write_note(d, "technical/ancient.md", "Retry policy", "cap", _stamp(3650))
    _write_page(d, "index.md", "# Index\n\ncap\n")
    _write_page(d, "activity-log/2026-01-01.md", "# Log\n\ncap\n")

    assert _ranked(d, "cap") == [
        "technical/ancient.md",
        "index.md",
        "activity-log/2026-01-01.md",
    ]


def test_a_note_without_an_updated_stamp_stays_in_the_result(tmp_path):
    """A note older than the stamp — or written by hand — is dated by its mtime,
    and never dropped from the result for lacking the key."""
    d = str(tmp_path / "journal")
    _write_note(d, "technical/unstamped.md", "Loose end", "backoff cap")

    assert _ranked(d, "backoff") == ["technical/unstamped.md"]


def test_a_note_with_no_readable_date_competes_at_the_half_life_value(tmp_path):
    """Neither a stamp nor an mtime is neutral, not zero: such a note must not
    rank below a two-month-old one, and must stay in the result. The paths sort
    against that order."""
    d = str(tmp_path / "journal")
    _write_note(d, "technical/z-dateless.md", "Loose end", "backoff cap")
    _write_note(d, "technical/a-older.md", "Second read", "backoff cap", _stamp(60))

    with patch("zrb.llm.tool.journal.os.path.getmtime", side_effect=OSError("gone")):
        assert _ranked(d, "backoff") == [
            "technical/z-dateless.md",
            "technical/a-older.md",
        ]


def test_a_stamp_the_writer_never_writes_is_still_aged(tmp_path):
    """A hand-written stamp may carry an offset, or not be a date at all. Neither
    may crash the age subtraction: the first is brought into local time, the
    second falls back to the file's mtime."""
    d = str(tmp_path / "journal")
    aware = datetime.now().astimezone().isoformat()
    _write_note(d, "technical/a-old.md", "Retry policy", "redis", _stamp(90))
    _write_note(d, "technical/y-garbled.md", "Queue depth", "redis", "last tuesday")
    _write_note(d, "technical/z-aware.md", "Cache keys", "redis", aware)
    old = (datetime.now() - timedelta(days=400)).timestamp()
    os.utime(os.path.join(d, "technical/y-garbled.md"), (old, old))

    assert _ranked(d, "redis") == [
        "technical/z-aware.md",
        "technical/a-old.md",
        "technical/y-garbled.md",
    ]
