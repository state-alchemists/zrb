"""Verify output-pane tail following and scrolling."""

from types import SimpleNamespace
from typing import Any

from prompt_toolkit.data_structures import Point
from prompt_toolkit.lexers import SimpleLexer
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType

from zrb.llm.ui.default.app.follow import OutputFollow, is_at_last_line
from zrb.llm.ui.default.app.keybinding import page_output
from zrb.llm.ui.default.app.layout import create_output_field


def _scroll(text_area, event_type):
    event = MouseEvent(
        position=Point(x=0, y=0),
        event_type=event_type,
        button=MouseButton.NONE,
        modifiers=frozenset(),
    )
    text_area.control.mouse_handler(event)


def _at_last_line(text_area) -> bool:
    doc = text_area.buffer.document
    return doc.cursor_position_row >= doc.line_count - 1


def test_wheel_up_leaves_last_line_then_wheel_down_returns():
    # Arrange: a multi-line output, cursor parked at the end (follow mode).
    text_area = create_output_field(
        "\n".join(f"L{i}" for i in range(10)), SimpleLexer()
    )
    assert _at_last_line(text_area)

    # Act + Assert: wheel up moves the cursor off the last line (freezes follow).
    _scroll(text_area, MouseEventType.SCROLL_UP)
    assert not _at_last_line(text_area)

    # Act + Assert: wheeling back down lands on the last line again (resumes).
    _scroll(text_area, MouseEventType.SCROLL_DOWN)
    _scroll(text_area, MouseEventType.SCROLL_DOWN)
    assert _at_last_line(text_area)


def test_the_wheel_tells_the_follow_state_where_the_reader_went():
    follow = OutputFollow()
    text_area = create_output_field(
        "\n".join(f"L{i}" for i in range(10)), SimpleLexer(), follow=follow
    )
    assert follow.following

    _scroll(text_area, MouseEventType.SCROLL_UP)
    assert not follow.following

    _scroll(text_area, MouseEventType.SCROLL_DOWN)
    _scroll(text_area, MouseEventType.SCROLL_DOWN)
    assert follow.following


def test_paging_tells_the_follow_state_where_the_reader_went():
    follow = OutputFollow()
    text_area = create_output_field(
        "\n".join(f"L{i}" for i in range(40)), SimpleLexer(), follow=follow
    )
    event: Any = SimpleNamespace(
        app=SimpleNamespace(
            output=SimpleNamespace(
                get_size=lambda: SimpleNamespace(rows=10),
            )
        )
    )

    page_output(text_area, event, -1, follow)
    assert not follow.following

    page_output(text_area, event, 1, follow)
    assert follow.following  # one screen down lands on the last line again

    page_output(text_area, event, -1, follow)
    page_output(text_area, event, -1, follow)
    page_output(text_area, event, 1, follow)
    assert not follow.following  # two screens up, one down: still short of the tail


def test_a_pane_with_no_follow_state_still_scrolls():
    # The field is built before any UI exists that could ask; scrolling it must
    # not need one.
    text_area = create_output_field(
        "\n".join(f"L{i}" for i in range(10)), SimpleLexer()
    )
    _scroll(text_area, MouseEventType.SCROLL_UP)
    assert not _at_last_line(text_area)


def test_is_at_last_line_reads_the_cursor_not_the_row_index():
    assert is_at_last_line(create_output_field("one\ntwo", SimpleLexer()))
    text_area = create_output_field("one\ntwo", SimpleLexer())
    text_area.buffer.cursor_position = 0
    assert not is_at_last_line(text_area)


def test_a_reader_scrolled_up_is_not_followed_on_the_next_append(editing_ui):
    field = editing_ui.output_field
    field.text = "one\ntwo\nthree\n"
    field.buffer.cursor_position = 0  # the reader is at the top

    editing_ui.append_to_output("four")

    assert editing_ui.output_follow.following is False
    assert field.buffer.cursor_position == 0


def test_a_reader_on_the_tail_keeps_following_the_append(editing_ui):
    field = editing_ui.output_field
    field.text = "one\n"
    field.buffer.cursor_position = len(field.text)

    editing_ui.append_to_output("two")

    assert editing_ui.output_follow.following is True
    assert field.buffer.cursor_position == len(field.text)
