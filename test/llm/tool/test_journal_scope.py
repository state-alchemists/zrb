"""Which notes a session is shown, by the repository it is working in.

The index spends one line per note, so a checkout's worth of notes crowds out
the rest unless the view is scoped. These tests pin the three ways that could go
wrong: a note about somewhere else arriving unasked, a note about the user
disappearing because it has no tag, and a line vanishing because the file it
links is not a note at all.
"""

import os
import subprocess
from datetime import datetime
from unittest.mock import patch

import pytest

from zrb.config.config import CFG
from zrb.llm.prompt.live_context import render_journal_index
from zrb.llm.tool.journal_index import elsewhere_lines, scope_index
from zrb.llm.tool.journal_note import Note
from zrb.llm.tool.journal_scope import (
    default_scope,
    is_in_scope,
    normalize_scope,
    repo_of,
    scope_argument,
)
from zrb.llm.util.git import repository_root_from_common_dir

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


def _note(rel: str, repo: str, day: int = 1) -> Note:
    return Note(
        category=rel.split("/")[0],
        slug=rel.split("/")[-1].removesuffix(".md"),
        title=rel,
        status="active",
        hud_line="a line",
        pinned=False,
        updated=datetime(2026, 10, day),
        has_stamp=True,
        repo=repo,
    )


def test_an_untagged_note_is_shown_wherever_you_are():
    """The field is new; a default that guessed would hide notes by the hundred."""
    assert is_in_scope("", "zrb") is True
    assert is_in_scope("", "lcicd") is True


def test_a_note_about_another_repository_is_compressed_not_deleted():
    """Working in one repository must not mean forgetting the others.

    Its lines leave the sections, and the work they represent is still named —
    how much of it there is, and its newest claim — so a session never re-plans
    work that already exists."""
    notes = [_note("technical/retries.md", "soda"), _note("technical/bank-job.md", "zrb")]
    rendered = scope_index(INDEX, notes, "zrb")
    assert "retries happen once ([note](technical/retries.md))" not in rendered
    assert "a bank job red at prepare is infra" in rendered
    assert elsewhere_lines(notes, "zrb") == [
        "- soda — 1 notes, newest (2026-10-01): a line"
    ]


def test_the_digest_names_one_line_per_other_repository_newest_first():
    notes = [
        _note("technical/a.md", "soda", day=2),
        _note("technical/b.md", "soda", day=9),
        _note("projects/c.md", "bank", day=5),
        _note("technical/d.md", "lcicd", day=1),
    ]
    assert elsewhere_lines(notes, "lcicd") == [
        "- soda — 2 notes, newest (2026-10-09): a line",
        "- bank — 1 notes, newest (2026-10-05): a line",
    ]


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
        # Not reserved: a repository really called `global` is a tag like any
        # other. Only the *argument* `global` means "no repository at all".
        ("global", "global"),
        ("", ""),
        ("  ", ""),
    ],
)
def test_a_tag_is_one_token(given, expected):
    assert normalize_scope(given) == expected


@pytest.mark.parametrize(
    "given, expected",
    [("global", ""), ("GLOBAL", ""), ("soda", "soda"), ("", "")],
)
def test_the_argument_global_means_no_tag(given, expected):
    assert scope_argument(given) == expected


@pytest.mark.parametrize(
    "common_dir, expected",
    [
        ("/work/zrb/.git", "/work/zrb"),
        ("/work/parent/.git/modules/service", "/work/parent/.git/modules/service"),
        ("", ""),
    ],
)
def test_a_repository_is_named_by_its_own_directory(common_dir, expected):
    """A worktree answers with the repository it belongs to; a submodule answers
    with itself, not with the `modules` directory the superproject keeps it in."""
    assert repository_root_from_common_dir(common_dir) == expected


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


def test_a_revision_keeps_the_repository_the_note_was_written_in(writable_journal):
    """A note is corrected from wherever the reader is, and that is not a move.

    Re-deriving the scope on a revision would drop a note about zrb out of every
    zrb session because it happened to be corrected from another checkout."""
    _write("technical", "build-cache")

    with patch("zrb.llm.tool.journal_write.repo_of", return_value="soda"):
        _write("technical", "build-cache")

    body = _write_note(writable_journal, "technical", "build-cache")
    assert "repo: zrb" in body


def test_a_new_note_from_another_repository_takes_that_repository(writable_journal):
    """The rule the revision case must not swallow: a brand-new note from soda is
    about soda."""
    with patch("zrb.llm.tool.journal_write.repo_of", return_value="soda"):
        _write("technical", "new-topic")

    body = _write_note(writable_journal, "technical", "new-topic")
    assert "repo: soda" in body


def test_an_explicit_repository_moves_a_note(writable_journal):
    """Saying so is allowed: an argument beats both the old tag and the default."""
    _write("technical", "build-cache")
    _write("technical", "build-cache", repo="soda")

    body = _write_note(writable_journal, "technical", "build-cache")
    assert "repo: soda" in body


def test_an_explicit_repository_wins(writable_journal):
    _write("technical", "retries", repo="Soda Local")
    body = _write_note(writable_journal, "technical", "retries")
    assert "repo: soda-local" in body


def test_global_is_how_a_technical_note_opts_out(writable_journal):
    _write("technical", "retries", repo="global")
    body = _write_note(writable_journal, "technical", "retries")
    assert "repo:" not in body


def test_a_batch_can_scope_the_notes_it_imports(writable_journal):
    """The batch seam reaches the same writer, so it has to reach the same tag.

    Otherwise an importer cannot say where the notes came from and every one of
    them lands in whichever checkout happened to run the import."""
    from zrb.llm.tool.journal_write import journal_transaction

    with journal_transaction() as transaction:
        transaction.write_note(
            "technical",
            "cache",
            "Cache",
            "ctx",
            "found",
            "s:1",
            applies_when="while the file exists",
            hud_line="the claim itself",
            repo="soda",
        )
        transaction.write_note(
            "technical",
            "queue",
            "Queue",
            "ctx",
            "found",
            "s:2",
            applies_when="while the file exists",
            hud_line="the claim itself",
        )

    assert "repo: soda" in _write_note(writable_journal, "technical", "cache")
    assert "repo: zrb" in _write_note(writable_journal, "technical", "queue")


def test_a_tilde_journal_directory_is_filtered_like_any_other(
    writable_journal, tmp_path, monkeypatch
):
    """The index file is read through `expanduser`, so the notes have to be listed
    through it too.

    A literal `~` finds no note, so nothing looks foreign and the other
    repository's lines stay in the index — the feature silently doing nothing for
    every journal configured the way this one is."""
    _write("technical", "bank-job", repo="soda")
    # `expanduser` reads HOME on POSIX and USERPROFILE here; both point the same
    # place so the test asserts the same thing on every runner.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(CFG, "LLM_JOURNAL_ENABLED", True, raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_DIR", "~/notes", raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_INDEX_FILE", "index.md", raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_INDEX_MAX_CHARS", 3600, raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_AUTO_SEARCH_ENABLED", False, raising=False)

    with patch("zrb.llm.tool.journal_scope.repo_of", return_value="zrb"):
        block = render_journal_index() or ""

    assert "## Other projects" in block
    # The line itself is gone from the sections; the tag is still named in the
    # digest, which is the whole point: compressed, not hidden.
    assert "([note](technical/bank-job.md))" not in block
