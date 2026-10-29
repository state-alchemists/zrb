"""The geometry of a docked panel: how tall it may be, and which rows it paints.

A panel docked into the layout spends the transcript's rows, so its height is a
share of the screen rather than whatever its content wants. Two of the three
panels render through a `FormattedTextControl`, which cannot scroll a `Buffer`:
the rows it returns are the window, so the slice has to follow the cursor itself.
"""

from prompt_toolkit.layout.dimension import to_dimension

from zrb.llm.ui.default.app.docking import (
    FRAME_ROWS,
    LAYOUT_MIN_ROWS,
    PANEL_MIN_ROWS,
    RowWindow,
    framed_panel_height,
    panel_content_height,
    panel_row_cap,
    rendered_row_count,
)


class _BareUI:
    """A UI with no live application, so only the terminal probe answers."""

    is_application_built = False


def _frags(count: int):
    return [("class:row", f"row {index}\n") for index in range(count)]


def _painted(frags) -> list[str]:
    return [line.strip() for line in "".join(f[1] for f in frags).split("\n") if line]


def test_rendered_row_count_counts_the_rows_a_paint_covers():
    assert rendered_row_count([]) == 0
    assert rendered_row_count([("class:x", "one\n")]) == 1
    assert rendered_row_count([("class:x", "one\ntwo\n")]) == 2
    # A last line without its newline still paints.
    assert rendered_row_count([("class:x", "one\ntwo")]) == 2
    # Separate fragments, one newline: still one row.
    assert rendered_row_count([("class:x", "one"), ("class:x", "\n")]) == 1


def test_the_cap_is_a_third_of_the_screen(terminal_rows):
    """CI runs 24 rows and a developer's terminal is taller, so pin both."""
    terminal_rows(24)
    assert panel_row_cap(_BareUI()) == 8
    terminal_rows(40)
    assert panel_row_cap(_BareUI()) == 13


def test_a_panel_keeps_four_rows_while_the_layout_can_spare_them(terminal_rows):
    terminal_rows(30)  # a third is 10, and the layout has 14 to spare
    assert panel_row_cap(_BareUI()) == 10
    assert panel_row_cap(_BareUI()) >= PANEL_MIN_ROWS


def test_a_short_screen_lowers_the_floor_rather_than_breaking_the_layout(
    terminal_rows,
):
    """The panel asks for rows the rest of the layout has already spent.

    Asking anyway would leave prompt_toolkit's "window too small" note where the
    chat should be, so the cap yields all the way to the rows that exist.
    """
    terminal_rows(LAYOUT_MIN_ROWS + 2)
    assert panel_row_cap(_BareUI()) == 2
    terminal_rows(LAYOUT_MIN_ROWS - 4)
    assert panel_row_cap(_BareUI()) == 0


def test_the_frame_height_is_exact_and_re_read_on_every_render():
    rows = [7]
    height = framed_panel_height(lambda: rows[0])
    assert to_dimension(height).preferred == 7 + FRAME_ROWS
    rows[0] = 2
    assert to_dimension(height).preferred == 2 + FRAME_ROWS


def test_a_panel_body_is_measured_without_a_frame_border():
    height = panel_content_height(lambda: 5)
    assert to_dimension(height).preferred == 5


class TestRowWindow:
    def test_a_window_at_least_as_tall_as_the_content_paints_all_of_it(self):
        window = RowWindow()
        assert _painted(window.slice(_frags(3), anchor=2, rows=10)) == [
            "row 0",
            "row 1",
            "row 2",
        ]

    def test_the_anchor_row_is_painted_even_when_it_is_the_last_one(self):
        window = RowWindow()
        painted = _painted(window.slice(_frags(20), anchor=12, rows=4))
        assert painted[-1] == "row 12"
        assert len(painted) == 4

    def test_the_offset_follows_the_cursor_down_and_back_up(self):
        window = RowWindow()
        assert _painted(window.slice(_frags(20), anchor=0, rows=4))[0] == "row 0"
        assert "row 12" in _painted(window.slice(_frags(20), anchor=12, rows=4))
        # Moving back up scrolls back: the anchor sits at the top of the window.
        assert _painted(window.slice(_frags(20), anchor=2, rows=4))[0] == "row 2"

    def test_the_last_row_is_reachable_without_overrunning_the_content(self):
        window = RowWindow()
        painted = _painted(window.slice(_frags(20), anchor=19, rows=4))
        assert painted == ["row 16", "row 17", "row 18", "row 19"]

    def test_no_rows_asked_for_paints_nothing(self):
        window = RowWindow()
        assert window.slice(_frags(20), anchor=3, rows=0) == []

    def test_reset_returns_the_next_question_to_the_top(self):
        window = RowWindow()
        window.slice(_frags(20), anchor=15, rows=4)
        window.reset()
        assert _painted(window.slice(_frags(20), anchor=0, rows=4))[0] == "row 0"
