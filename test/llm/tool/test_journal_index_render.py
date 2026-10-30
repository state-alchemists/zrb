"""The journal indexes are rendered from the notes, and carry foreign lines.

A note's frontmatter says what its index entries are; a write, supersede, delete
or refile changes the note and renders again. A line in a generated region that
no note accounts for is a hand edit, and the render leaves it alone.
"""

import os
from unittest.mock import patch

import pytest

from zrb.llm.tool import journal_write
from zrb.llm.tool.journal_write import (
    delete_journal_note,
    journal_transaction,
    log_activity,
    supersede_journal_note,
    write_journal_note,
)


@pytest.fixture
def writable_journal(tmp_path):
    """Patch CFG for the writer module and return the journal root."""
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 25
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        yield str(root)


def _read(root: str, relative: str = "index.md") -> str:
    with open(os.path.join(root, relative), "r", encoding="utf-8") as f:
        return f.read()


def _edit(root: str, relative: str, old: str, new: str) -> None:
    text = _read(root, relative)
    assert old in text
    with open(os.path.join(root, relative), "w", encoding="utf-8") as f:
        f.write(text.replace(old, new, 1))


def _section(root: str, name: str) -> list[str]:
    body = _read(root).split(f"## {name}\n", 1)[1].split("\n## ", 1)[0]
    return [line for line in body.splitlines() if line.strip()]


def _note(
    slug, hud_line=None, category="user", pinned=False, applies_when="while tested", **extra
) -> str:
    return write_journal_note(
        category=category,
        slug=slug,
        title=slug.title(),
        context="c",
        finding="f",
        source="s",
        hud_line=hud_line,
        pinned=pinned,
        applies_when=applies_when,
        **extra,
    )


def test_a_note_keeps_its_index_facts_in_its_frontmatter(writable_journal):
    _note("identity", "Goes by Go.", pinned=True)

    head = _read(writable_journal, "user/identity.md").split("\n---\n")[0]
    assert "hud_line: Goes by Go." in head
    assert "pinned: true" in head
    assert "updated: " in head


def test_editing_a_notes_frontmatter_changes_the_index_at_the_next_render(
    writable_journal,
):
    _note("identity", "Goes by Go.")
    _edit(writable_journal, "user/identity.md", "Goes by Go.", "Goes by Gofren.")

    log_activity("anything")

    assert _section(writable_journal, "User") == [
        "- Goes by Gofren. ([note](user/identity.md))"
    ]


def test_a_foreign_line_survives_a_write(writable_journal):
    _note("seed", "Seeded.")
    _edit(writable_journal, "index.md", "## User\n", "## User\n\n- A hand note.\n")

    _note("identity", "Goes by Go.")

    assert _section(writable_journal, "User") == [
        "- A hand note.",
        "- Goes by Go. ([note](user/identity.md))",
        "- Seeded. ([note](user/seed.md))",
    ]


def test_a_foreign_line_does_not_move_among_the_other_foreign_lines(
    writable_journal,
):
    journal_write.ensure_journal_tree()
    _edit(
        writable_journal,
        "index.md",
        "## User\n",
        "## User\n\n- First hand note.\n- Second hand note.\n",
    )

    for slug in ("a", "b"):
        _note(slug, f"Line {slug}.")

    section = _section(writable_journal, "User")
    assert section.index("- First hand note.") < section.index("- Second hand note.")
    assert len(section) == 4


def test_a_foreign_line_is_not_evicted_and_does_not_count_toward_the_cap(
    writable_journal,
):
    journal_write.CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 2
    journal_write.ensure_journal_tree()
    _edit(writable_journal, "index.md", "## User\n", "## User\n\n- A hand note.\n")

    results = [_note(f"n{i}", f"Line {i}.") for i in range(3)]

    section = _section(writable_journal, "User")
    assert "- A hand note." in section
    # Two owned lines under the cap, plus the one foreign line.
    assert len(section) == 3
    assert "Line 0." not in "".join(section)
    assert "Evicted from ## User (cap 2)" in results[2]
    assert "A hand note" not in results[2]


def test_a_foreign_line_survives_a_supersede(writable_journal):
    _note("old", "A fact that stops.")
    _edit(writable_journal, "index.md", "## User\n", "## User\n\n- A hand note.\n")

    supersede_journal_note("user", "old", "no longer true")

    assert _section(writable_journal, "User") == ["- A hand note."]


@pytest.mark.parametrize(
    "anchor, hand_line",
    [
        ("## User\n", "- A hand note."),
        ("## Constraints\n", "- A hand constraint."),
        ("## Agent\n", "- A hand agent rule."),
        ("## Recent\n", "- A hand headline."),
        ("(activity-log/index.md)\n", "- [External](elsewhere/index.md)"),
        ("## Recent Insights\n", "- [Hand link](https://example.com)"),
    ],
)
def test_a_hand_edit_in_each_generated_region_of_the_root_index_survives(
    writable_journal, anchor, hand_line
):
    _note("seed", "Seeded.", category="technical")
    _edit(writable_journal, "index.md", anchor, f"{anchor}\n{hand_line}\n")

    _note("identity", "Goes by Go.")
    supersede_journal_note("technical", "seed", "retired")
    delete_journal_note("user", "identity")

    assert hand_line in _read(writable_journal).splitlines()


def test_a_hand_edit_in_a_category_index_survives(writable_journal):
    _note("seed", "Seeded.")
    with open(os.path.join(writable_journal, "user", "index.md"), "a") as f:
        f.write("\nSee also the handbook.\n- [Handbook](../handbook.md)\n")

    _note("identity", "Goes by Go.")
    delete_journal_note("user", "identity")

    index = _read(writable_journal, "user/index.md")
    assert "See also the handbook." in index
    assert "- [Handbook](../handbook.md)" in index
    assert "- [Seed](seed.md)" in index


def test_rendering_twice_yields_the_same_bytes(writable_journal):
    _note("identity", "Goes by Go.")
    _note("rule", "Tests stay public.", category="technical", pinned=True)
    _edit(writable_journal, "index.md", "## Agent\n", "## Agent\n\n- A hand note.\n")

    log_activity("first")
    snapshot = {
        name: _read(writable_journal, name)
        for name in ("index.md", "user/index.md", "technical/index.md")
    }
    log_activity("second")

    for name, text in snapshot.items():
        assert _read(writable_journal, name) == text


def test_refiling_a_note_moves_its_line_instead_of_copying_it(writable_journal):
    _note("rule", "Keep this.", category="technical")
    assert _section(writable_journal, "Recent") == [
        "- Keep this. ([note](technical/rule.md))"
    ]

    _note("rule", "Keep this.", category="technical", pinned=True)

    assert _section(writable_journal, "Recent") == []
    assert _section(writable_journal, "Constraints") == [
        "- 📌 Keep this. ([note](technical/rule.md))"
    ]


def test_a_write_without_a_line_keeps_the_notes_line_and_its_pin(writable_journal):
    _note("rule", "Keep this.", category="technical", pinned=True)

    _note("rule", None, category="technical")

    assert _section(writable_journal, "Constraints") == [
        "- 📌 Keep this. ([note](technical/rule.md))"
    ]


def test_superseding_drops_the_line_from_the_root_but_not_the_category_index(
    writable_journal,
):
    _note("old", "A fact that stops.", category="technical")

    result = supersede_journal_note("technical", "old", "no longer true")

    root = _read(writable_journal)
    assert "old.md" not in root
    assert "[Old](old.md)" in _read(writable_journal, "technical/index.md")
    assert (
        "Removed from the index: - A fact that stops. ([note](technical/old.md))"
        in (result)
    )


def test_deleting_a_note_removes_it_from_every_index(writable_journal):
    _note("gone", "A fact to retract.", category="technical", pinned=True)
    _note("kept", "A fact to keep.", category="technical")

    delete_journal_note("technical", "gone")

    assert "gone" not in _read(writable_journal)
    assert "gone" not in _read(writable_journal, "technical/index.md")
    assert "kept.md" in _read(writable_journal)


def test_a_rolled_back_transaction_restores_the_indexes_and_the_notes(
    writable_journal,
):
    _note("seed", "Seeded.")
    before = {
        name: _read(writable_journal, name) for name in ("index.md", "user/index.md")
    }

    with pytest.raises(RuntimeError):
        with journal_transaction() as batch:
            batch.write_note(
                "user", "extra", "Extra", "c", "f", "s", hud_line="New.",
                applies_when="while zrb 3.29 is released",
            )
            batch.delete_note("user", "seed")
            raise RuntimeError("abort")

    for name, text in before.items():
        assert _read(writable_journal, name) == text
    assert os.path.isfile(os.path.join(writable_journal, "user", "seed.md"))
    assert not os.path.exists(os.path.join(writable_journal, "user", "extra.md"))


def test_the_cap_evicts_the_oldest_line_and_a_revision_refreshes_it(writable_journal):
    journal_write.CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 2
    _note("a", "Line a.")
    _note("b", "Line b.")
    _note("a", "Line a, revised.")

    result = _note("c", "Line c.")

    section = _section(writable_journal, "User")
    assert section == [
        "- Line c. ([note](user/c.md))",
        "- Line a, revised. ([note](user/a.md))",
    ]
    assert '"Line b. ([note](user/b.md))"' in result


def test_an_evicted_line_is_a_view_and_returns_when_the_cap_is_raised(
    writable_journal,
):
    journal_write.CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 1
    _note("a", "Line a.")
    _note("b", "Line b.")
    assert "Line a." not in _read(writable_journal)

    journal_write.CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 5
    log_activity("anything")

    assert _section(writable_journal, "User") == [
        "- Line b. ([note](user/b.md))",
        "- Line a. ([note](user/a.md))",
    ]


def test_a_hand_edit_to_the_text_of_a_notes_own_line_is_reverted(writable_journal):
    """The line's text is the note's `hud_line`, so that is where to edit it."""
    _note("identity", "Goes by Go.")
    _edit(writable_journal, "index.md", "Goes by Go.", "Goes by someone else.")

    log_activity("anything")

    assert _section(writable_journal, "User") == [
        "- Goes by Go. ([note](user/identity.md))"
    ]


def test_deleting_a_note_also_drops_a_hand_written_link_to_it(writable_journal):
    """A line that is nothing but a link to the note would be a broken link."""
    _note("gone", None, category="technical")
    _edit(
        writable_journal,
        "index.md",
        "## Recent\n",
        "## Recent\n\n- [the note](technical/gone.md)\n- Unrelated hand note.\n",
    )

    delete_journal_note("technical", "gone")

    assert _section(writable_journal, "Recent") == ["- Unrelated hand note."]


def test_retitled_note_is_relabelled_not_duplicated_in_indexes(writable_journal):
    for title in ("Aug review", "Sep review"):
        write_journal_note(
            "technical",
            "prompt-review",
            title,
            "c",
            "f",
            "s",
            applies_when="while zrb 3.29 is released",
        )

    # Two lines name the note now — its HUD line and its catalog line — so the
    # count is per region: one catalog entry and one category entry, relabelled.
    root = _read(writable_journal)
    assert root.count("- [Sep review](technical/prompt-review.md)") == 1
    assert "[Aug review]" not in root
    category_index = _read(writable_journal, "technical/index.md")
    assert category_index.count("- [Sep review](prompt-review.md)") == 1
    assert "[Aug review]" not in category_index


def test_retitling_a_note_whose_title_contains_a_bracket_relabels_not_duplicates(
    writable_journal,
):
    """A title is free-form model text, so a `]` in it must not hide the line
    from the target-keyed lookup that registration is keyed on."""
    for title in ("Fixes [nested] brackets", "Fixes [nested] brackets, revised"):
        write_journal_note(
            "technical",
            "nested",
            title,
            "c",
            "f",
            "s",
            applies_when="while zrb 3.29 is released",
        )

    category_index = _read(writable_journal, "technical/index.md")
    assert category_index.count("nested.md)") == 1
    assert "- [Fixes [nested] brackets, revised](nested.md)" in category_index
    # The root index names the note twice too, so the count is of catalog
    # entries, not of every mention.
    root = _read(writable_journal)
    assert root.count("- [Fixes [nested] brackets, revised](technical/nested.md)") == 1
    assert "[Fixes [nested] brackets](" not in root
