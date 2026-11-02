"""Which notes a session is shown, by the repository it is working in.

The index spends one line per note, so a checkout's worth of notes crowds out
the rest unless the view is scoped. These tests pin the three ways that could go
wrong: a note about somewhere else arriving unasked, a note about the user
disappearing because it has no tag, and a line vanishing because the file it
links is not a note at all.
"""

import os
import subprocess
from unittest.mock import patch

import pytest

from zrb.llm.tool.journal_index import scope_index
from zrb.llm.tool.journal_note import Note
from zrb.llm.tool.journal_scope import (
    default_scope,
    is_in_scope,
    normalize_scope,
    repo_of,
)

INDEX = """# Journal

## User

- how we talk ([note](preferences/how-we-talk.md))

## Constraints

- the runner helper is infra ([note](technical/runner-helper.md))
- a bank job red at prepare is infra ([note](technical/bank-job.md))

## Recent

- retries happen once ([note](technical/retries.md))
- a hand-written line nobody owns
"""


def _note(rel: str, repo: str) -> Note:
    return Note(
        category=rel.split("/")[0],
        slug=rel.split("/")[-1].removesuffix(".md"),
        title=rel,
        status="active",
        hud_line="a line",
        pinned=False,
        updated=None,
        has_stamp=False,
        repo=repo,
    )


def test_an_untagged_note_is_shown_wherever_you_are():
    """The field is new; a default that guessed would hide notes by the hundred."""
    assert is_in_scope("", "zrb") is True
    assert is_in_scope("", "lcicd") is True


def test_a_note_about_another_repository_is_not_injected():
    notes = [_note("technical/retries.md", "soda"), _note("technical/bank-job.md", "zrb")]
    rendered = scope_index(INDEX, notes, "zrb")
    assert "retries happen once" not in rendered
    assert "a bank job red at prepare is infra" in rendered


def test_a_section_whose_lines_all_left_leaves_with_them():
    """An empty `## Constraints` says a constraint exists and not what it is."""
    notes = [
        _note("technical/runner-helper.md", "soda"),
        _note("technical/bank-job.md", "soda"),
    ]
    rendered = scope_index(INDEX, notes, "zrb")
    assert "## Constraints" not in rendered
    assert "## Recent" in rendered


def test_a_line_that_links_no_note_stays():
    """Hand edits and overflow markers are carried through, as the renderer does."""
    notes = [_note("technical/retries.md", "soda")]
    rendered = scope_index(INDEX, notes, "zrb")
    assert "a hand-written line nobody owns" in rendered


def test_a_line_linking_a_file_that_is_not_a_note_stays():
    """A link to a file with no `slug:` is not a note, so nothing is known about
    where it belongs — and nothing known is dropped."""
    rendered = scope_index(INDEX, [], "zrb")
    assert "retries happen once" in rendered
    assert "how we talk" in rendered


def test_outside_a_repository_everything_is_shown():
    """A chat opened in no checkout has no better filter than none."""
    notes = [_note("technical/retries.md", "soda")]
    assert scope_index(INDEX, notes, "") == INDEX.rstrip("\n")


@pytest.mark.parametrize(
    "given, expected",
    [
        ("ZRB", "zrb"),
        (" Soda Local ", "soda-local"),
        ("soda.local", "soda.local"),
        ("global", ""),
        ("", ""),
        ("  ", ""),
    ],
)
def test_a_tag_is_one_token(given, expected):
    assert normalize_scope(given) == expected


@pytest.mark.parametrize(
    "category, expected",
    [
        ("technical", "zrb"),
        ("projects", "zrb"),
        ("user", ""),
        ("preferences", ""),
        ("agent", ""),
    ],
)
def test_a_note_about_a_person_travels_with_the_person(category, expected):
    assert default_scope(category, "zrb") == expected


def test_a_repository_answers_with_its_own_name(tmp_path):
    """The tag has to match the directory a person would name, not a worktree's
    branch: every worktree of one repository must answer the same."""
    root = tmp_path / "soda"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    assert repo_of(str(root)) == "soda"


def test_no_repository_answers_with_nothing(tmp_path):
    assert repo_of(str(tmp_path)) == ""


def _write_note(root: str, category: str, slug: str) -> str:
    path = os.path.join(root, category, f"{slug}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def writable_journal(tmp_path):
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 25
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        with patch(
            "zrb.llm.tool.journal_write.repo_of", return_value="zrb"
        ):
            yield str(root)


def _write(category: str, slug: str, repo: str | None = None) -> str:
    from zrb.llm.tool.journal_write import write_journal_note

    return write_journal_note(
        category=category,
        slug=slug,
        title="A title",
        context="When it applies.",
        finding="The finding.",
        source="src/zrb/llm/tool/journal_note.py:52",
        hud_line="the claim itself",
        applies_when="while the file exists",
        repo=repo,
    )


def test_a_technical_note_takes_the_repository_in_hand(writable_journal):
    _write("technical", "retries")
    body = _write_note(writable_journal, "technical", "retries")
    assert "repo: zrb" in body


def test_a_note_about_the_user_carries_no_tag(writable_journal):
    _write("user", "how-we-talk")
    body = _write_note(writable_journal, "user", "how-we-talk")
    assert "repo:" not in body


def test_an_explicit_repository_wins(writable_journal):
    _write("technical", "retries", repo="Soda Local")
    body = _write_note(writable_journal, "technical", "retries")
    assert "repo: soda-local" in body


def test_global_is_how_a_technical_note_opts_out(writable_journal):
    _write("technical", "retries", repo="global")
    body = _write_note(writable_journal, "technical", "retries")
    assert "repo:" not in body
