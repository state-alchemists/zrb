"""The choice panel docked in the input frame's place instead of floating.

A choice makes the input field dead — printable keys reach it only outside a
choice — so the panel takes the input's rows. That puts its height on the
transcript's budget, so a twenty-option question is capped and scrolls under
the cursor rather than eating the screen.
"""

from __future__ import annotations

from types import SimpleNamespace

from prompt_toolkit.layout.dimension import to_dimension
from prompt_toolkit.widgets import Frame

from zrb.llm.ui.default.app.docking import FRAME_ROWS, panel_row_cap


def _spec(options, context=None):
    spec = {
        "question": "Which one?",
        "options": options,
        "multi_select": False,
        "header": "Pick",
        "index": 1,
        "total": 1,
    }
    if context is not None:
        spec["context"] = context
    return spec


def _options(count: int) -> list[dict]:
    return [{"label": f"Option {index}"} for index in range(count)]


def _rendered(ui) -> str:
    return "".join(frag[1] for frag in ui.get_choice_text())


def _event(text: str):
    """The Enter the input field would send with *text* in its buffer."""
    return SimpleNamespace(
        current_buffer=SimpleNamespace(text=text, reset=lambda: None)
    )


def test_the_panel_keeps_the_frames_title_and_style_class(ui):
    ui.begin_choice(_spec(_options(2)))
    panel = ui.choice_panel()

    assert isinstance(panel, Frame)
    assert panel.title == "Select an answer"
    assert "class:choice-frame" in panel.container.style


def test_the_frame_is_exactly_the_panels_rows_plus_its_border(ui, terminal_rows):
    terminal_rows(24)
    ui.begin_choice(_spec(_options(2)))
    panel = ui.choice_panel()

    assert to_dimension(panel.container.height).preferred == ui.panel_rows() + FRAME_ROWS


def test_a_twenty_option_question_is_capped_at_a_third_of_the_screen(
    ui, terminal_rows
):
    """Twenty options must not take the rows the transcript needs to be read."""
    terminal_rows(24)
    ui.begin_choice(_spec(_options(20)))
    assert ui.panel_rows() == panel_row_cap(ui) == 8
    assert _rendered(ui).count("\n") == 8


def test_five_and_twenty_options_paint_the_same_height(ui, terminal_rows):
    """The panel is a fixed height, not one that grows with the question."""
    terminal_rows(24)
    ui.begin_choice(_spec(_options(5)))
    five = ui.panel_rows()
    ui.begin_choice(_spec(_options(20)))
    assert ui.panel_rows() == five


def test_the_painted_rows_follow_the_cursor_past_the_cap(ui, terminal_rows):
    terminal_rows(24)
    ui.begin_choice(_spec(_options(20)))
    ui.move_choice_cursor(15)

    text = _rendered(ui)
    assert "Option 15" in text, "the selected option must stay in view"
    assert "Option 0" not in text, "the first option scrolled out of the panel"
    assert "❯" in text


def test_the_highlighted_row_survives_the_tightest_slice(ui, terminal_rows):
    """Two painted rows still hold the option the cursor is on."""
    terminal_rows(18)
    ui.begin_choice(_spec(_options(20)))
    ui.move_choice_cursor(10)

    text = _rendered(ui)
    assert "Option 10" in text
    assert len([line for line in text.split("\n") if line.strip()]) <= 2


def test_a_fresh_choice_starts_at_the_top_again(ui, terminal_rows):
    terminal_rows(24)
    ui.begin_choice(_spec(_options(20)))
    ui.move_choice_cursor(15)
    assert "Option 0" not in _rendered(ui)

    ui.begin_choice(_spec(_options(20)))
    assert "Option 0" in _rendered(ui)


def test_at_forty_rows_a_normal_question_shows_in_full(ui, terminal_rows):
    terminal_rows(40)
    ui.begin_choice(_spec(_options(2)))
    text = _rendered(ui)

    assert "Which one?" in text
    assert "Option 0" in text and "Option 1" in text
    assert "Type my own answer" in text
    assert "↑/↓ move" in text, "the key hint is not cut off at this height"
    assert ui.panel_rows() < panel_row_cap(ui), "nothing had to be cut"


def test_at_forty_rows_the_context_shows_above_the_question(ui, terminal_rows):
    terminal_rows(40)
    ui.begin_choice(_spec(_options(2), context="Two replicas, one region."))
    text = _rendered(ui)

    assert text.index("Two replicas") < text.index("Which one?")
    assert ui.panel_rows() <= panel_row_cap(ui)
    assert "↑/↓ move" in text


def test_the_hint_and_its_legend_survive_the_cap(ui, terminal_rows):
    """At 24 rows the free-text row scrolls out, but the hint stays: it carries
    the ★ legend, and an unexplained marker is worse than a scrolled option."""
    terminal_rows(24)
    spec = _spec([{"label": "Recommended one", "recommended": True}, {"label": "Other"}])
    ui.begin_choice(spec)
    text = _rendered(ui)

    assert "★ recommended" in text
    assert "↑/↓ move" in text
    assert "Recommended one" in text, "the cursor's own row stays too"


def test_a_short_screen_drops_the_context_and_keeps_the_option_row(ui, terminal_rows):
    """The options matter more than the context, and scrollback keeps the rest."""
    terminal_rows(18)
    ui.begin_choice(
        _spec(_options(2), context="Sentence 0 explains one fact at length. " * 8)
    )
    text = _rendered(ui)

    assert "explains one fact" not in text
    assert "Option 0" in text


def test_a_terminal_with_no_room_asks_in_the_transcript_instead(ui, terminal_rows):
    """A zero-row panel is a bare frame with nothing under it.

    The panel stands in the input frame's place, so at that size the user would
    lose both the options and the input. The question goes to the transcript and
    the choice closes — an active choice is what makes the input read-only and
    what makes Enter confirm the highlighted option — so the typed answer is the
    one that gets resolved, through the same pending capture the free-text row
    leaves behind.
    """
    terminal_rows(16)
    assert panel_row_cap(ui) == 0

    ui.begin_choice(_spec(_options(2)))

    assert ui.has_active_choice() is False
    printed = "".join(ui.echoes)
    assert "Which one?" in printed
    assert "Option 0" in printed and "Option 1" in printed
    assert "Type your answer and press Enter" in printed

    ui.handle_confirmation(_event("Option 1"))

    assert ui.resolved == "Option 1"
