"""`SearchJournal`'s summary line (`zrb/llm/tool/journal.py`)."""

import os
from unittest.mock import patch

import pytest

from zrb.llm.tool.journal import search_journal


@pytest.fixture
def journal_dir(tmp_path):
    d = tmp_path / "journal"
    d.mkdir()
    return str(d)


def _search_notes_saying(journal_dir, count, query):
    for index in range(count):
        with open(os.path.join(journal_dir, f"note-{index}.md"), "w") as f:
            f.write("compaction\n")
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = journal_dir
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            return search_journal(query)


def test_summary_says_how_many_rows_it_shows_when_matches_were_cut(journal_dir):
    result = _search_notes_saying(journal_dir, 8, "compaction")
    assert len(result["results"]) == 5
    assert result["summary"] == "Found 8 matches in 8 files. Showing 5."


def test_summary_omits_the_shown_count_when_every_match_is_listed(journal_dir):
    result = _search_notes_saying(journal_dir, 2, "compaction")
    assert len(result["results"]) == 2
    assert result["summary"] == "Found 2 matches in 2 files."
