"""The output pane follows the tail until the wheel scrolls it up.

Scrolling is implemented as moving the (cursor-pinned) output cursor, and
auto-follow in `append_to_output` is gated on the cursor sitting on the last
line. These tests cover that contract through the public widget.
"""

from prompt_toolkit.data_structures import Point
from prompt_toolkit.lexers import SimpleLexer
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType

from zrb.llm.app.layout import create_output_field


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
