"""What the ranking does with a file under a category directory that is not a note."""

import os
from datetime import datetime
from unittest.mock import patch

from zrb.llm.tool.journal import find_in_journal


def _page(root: str, rel: str, text: str) -> None:
    """A hand-written page: no frontmatter `slug`, so not a note."""
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _note(root: str, rel: str, body: str, pinned: bool = False) -> None:
    """A note written just now, so its age cannot decide the order."""
    front = [
        f"slug: {rel.rsplit('/', 1)[-1].removesuffix('.md')}",
        f"updated: {datetime.now().isoformat(timespec='microseconds')}",
    ]
    if pinned:
        front.append("pinned: true")
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        block = "".join(f"{line}\n" for line in front)
        f.write(f"---\n{block}---\n# Note\n\n{body}\n")


def _ranked(root: str, query: str) -> list[str]:
    """The files a search returns, in rank order, each named once.

    `find_in_journal`, not `search_journal`: recording a usage event writes to
    the real store, and ordering is this module's job."""
    with patch("zrb.llm.tool.journal.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = root
        with patch("zrb.llm.tool.journal.shutil.which", return_value=None):
            result = find_in_journal(query)
    files: list[str] = []
    for row in result.get("results", []):
        if row["file"] not in files:
            files.append(row["file"])
    return files


def test_a_hand_written_page_does_not_take_a_note_s_rank(tmp_path):
    """A page in a category directory carries no `slug:`, which is what the
    journal uses to tell a note from a page. Pinned, it used to score the pin
    boost like a note, tie a pinned note, and win the tie-break on its name —
    taking one of the five result slots from a note that is indexed."""
    root = str(tmp_path)
    _page(root, "technical/a-page.md", "---\npinned: true\n---\n# Page\n\nretry policy\n")
    _note(root, "technical/z-note.md", "retry policy", pinned=True)

    assert _ranked(root, "retry policy") == [
        "technical/z-note.md",
        "technical/a-page.md",
    ]
