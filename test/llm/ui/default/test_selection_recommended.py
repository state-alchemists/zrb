"""The `recommended` marker on a choice option.

A decision should say which option is advised. The ★ sits in the row's gutter,
so it is visible without becoming part of the label the answer resolves to.
"""

from __future__ import annotations


def _spec(options, multi=False, index=1, total=1):
    return {
        "question": "Which DB?",
        "options": options,
        "multi_select": multi,
        "header": "DB",
        "index": index,
        "total": total,
    }


def _rendered(ui) -> str:
    return "".join(frag[1] for frag in ui.get_choice_text())


def _row_line(ui, needle: str) -> str:
    """The one painted line carrying *needle*."""
    matches = [line for line in _rendered(ui).split("\n") if needle in line]
    assert len(matches) == 1, f"expected one line with {needle!r}, got {matches}"
    return matches[0]


def test_recommended_option_carries_a_marker_in_its_row(ui):
    ui.begin_choice(
        _spec(
            [
                {"label": "Postgres", "recommended": True},
                {"label": "SQLite"},
            ]
        )
    )
    assert "★" in _row_line(ui, "Postgres")
    assert "★" not in _row_line(ui, "SQLite")
    assert "★ recommended" in _rendered(ui), "the marker needs a legend"


def test_multi_select_marks_each_recommended_option(ui):
    ui.begin_choice(
        _spec(
            [
                {"label": "Tests", "recommended": True},
                {"label": "Docs"},
                {"label": "Lint", "recommended": True},
            ],
            multi=True,
        )
    )
    assert "★" in _row_line(ui, "Tests")
    assert "★" in _row_line(ui, "Lint")
    assert "★" not in _row_line(ui, "Docs")


def test_no_legend_without_a_recommendation(ui):
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    assert "recommended" not in _rendered(ui)


def test_answering_a_recommended_option_resolves_to_the_plain_label(ui):
    """The ★ lives in the gutter, so it never reaches the answer."""
    ui.begin_choice(
        _spec(
            [
                {"label": "Postgres"},
                {"label": "SQLite", "recommended": True},
            ]
        )
    )
    ui.move_choice_cursor(1)
    ui.confirm_choice()

    assert ui.resolved == "SQLite"
    assert "✔ SQLite" in "".join(ui.echoes)


def test_answering_recommended_options_in_multi_select_resolves_plain_labels(ui):
    ui.begin_choice(
        _spec(
            [
                {"label": "Tests", "recommended": True},
                {"label": "Docs"},
                {"label": "Lint", "recommended": True},
            ],
            multi=True,
        )
    )
    ui.toggle_choice_current()
    ui.move_choice_cursor(2)
    ui.toggle_choice_current()
    ui.confirm_choice()

    assert ui.resolved == "Tests, Lint"
