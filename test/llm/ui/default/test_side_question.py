"""The `/btw` panel: one question, one answer, closed by Esc.

The panel owns only its own state and text; where it sits on screen is the
`Float` the default `UI` builds around `side_question_window`. The keys it
receives while it holds the focus are pinned here too, because that is the
behaviour the focus buys: the movement keys scroll the answer instead of
recalling a message, and a printable key still starts one.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.ui.default.side_question import PANEL_PAGE_ROWS, UISideQuestion


class _FakeUI:
    """The bits of the default `UI` the panel reads."""

    def __init__(self, is_waiting_for_answer: bool = False):
        self.input_field = MagicMock(name="input_field")
        self.output_field_width = 80
        self.is_waiting_for_answer = is_waiting_for_answer
        self.insert_input_text = MagicMock(name="insert_input_text")

    def render_markdown(self, text: str, width: int | None = None) -> str:
        return f"<md width={width}>{text}</md>"


@pytest.fixture(autouse=True)
def no_application():
    """A unit test runs without a prompt_toolkit application to move the focus
    in. The tests that care which widget it names patch the same seam again."""
    with patch("zrb.llm.ui.default.side_question.focus_widget"):
        yield


@pytest.fixture
def part() -> UISideQuestion:
    panel = UISideQuestion(_FakeUI())
    panel.init_side_question_state()
    return panel


def _window(part: UISideQuestion):
    window = part.side_question_window
    assert window is not None
    return window


def _text(part: UISideQuestion) -> str:
    return _window(part).buffer.text


def _cursor_row(part: UISideQuestion) -> int:
    """The line the panel has scrolled to — its window follows the cursor."""
    return _window(part).buffer.document.cursor_position_row


def _last_row(part: UISideQuestion) -> int:
    return _text(part).count("\n")


def _press(part: UISideQuestion, key: str) -> None:
    """Deliver *key* the way the running application does.

    The panel holds the focus while it is shown, so its own control bindings
    answer the keypress; the last matching binding wins, as in prompt_toolkit.
    """
    window = _window(part)
    event = MagicMock(name="event")
    event.data = key
    event.current_buffer = window.buffer
    for binding in reversed(window.control.key_bindings.get_bindings_for_keys((key,))):
        if binding.filter():
            binding.handler(event)
            return
    raise AssertionError(f"the panel binds no {key!r}")


def test_nothing_is_shown_before_a_question_is_asked(part):
    assert part.is_active is False
    assert _text(part) == ""


def test_begin_shows_the_question_and_says_the_answer_is_coming(part):
    part.begin("why is the sky blue?")

    assert part.is_active is True
    assert _text(part).startswith("💭 why is the sky blue?")
    assert "thinking" in _text(part)


def test_end_renders_the_answer_at_the_pane_width_and_keeps_the_question(part):
    part.begin("why?")

    part.end("because of Rayleigh scattering")

    assert _text(part).startswith("💭 why?")
    assert "<md width=80>because of Rayleigh scattering</md>" in _text(part)


def test_fail_says_why_the_question_could_not_be_answered(part):
    part.begin("why?")

    part.fail("RuntimeError: provider down")

    assert "❌ RuntimeError: provider down" in _text(part)


def test_dismiss_closes_the_panel_and_gives_the_input_its_focus_back():
    ui = _FakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    with patch("zrb.llm.ui.default.side_question.focus_widget") as focus:
        part.begin("why?")
        focus.reset_mock()
        part.dismiss()

    assert part.is_active is False
    assert _text(part) == ""
    focus.assert_called_once_with(ui.input_field, "Input-field")


def test_begin_moves_the_focus_to_the_panel():
    """Every key the user presses then reaches the panel's own bindings, so
    Up/Down scroll the answer instead of recalling a message into the input."""
    ui = _FakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    with patch("zrb.llm.ui.default.side_question.focus_widget") as focus:
        part.begin("why?")

    focus.assert_called_once_with(part.side_question_window, "Side-question")
    assert part.is_active is True


def test_a_pending_prompt_also_keeps_the_focus():
    """`/btw` is routed ahead of a pending approval, so the panel can open over
    one. That field is what the turn is blocked on and keeps the focus."""
    panel = UISideQuestion(_FakeUI(is_waiting_for_answer=True))
    panel.init_side_question_state()
    with patch("zrb.llm.ui.default.side_question.focus_widget") as focus:
        panel.begin("why?")

    focus.assert_not_called()
    assert panel.is_active is True


def test_a_long_answer_scrolls_inside_a_fixed_height(part):
    from zrb.llm.ui.default.side_question import PANEL_HEIGHT

    part.begin("why?")
    part.end("\n".join(f"line {i}" for i in range(200)))

    window = part.side_question_window
    assert window is not None
    # A `TextArea` forwards its height to the `Window` it renders through.
    assert window.window.height == PANEL_HEIGHT


def test_an_answer_for_a_replaced_question_is_dropped(part):
    """A slower first `/btw` must not overwrite the panel a newer one opened."""
    first = part.begin("first question")
    part.begin("second question")

    part.end("the first answer", first)

    assert _text(part).startswith("💭 second question")
    assert "the first answer" not in _text(part)
    assert "thinking" in _text(part)


def test_a_failure_for_a_replaced_question_is_dropped(part):
    first = part.begin("first question")
    part.begin("second question")

    part.fail("RuntimeError: provider down", first)

    assert "❌" not in _text(part)
    assert _text(part).startswith("💭 second question")


def test_the_current_questions_answer_is_shown(part):
    request = part.begin("why?")

    part.end("because", request)

    assert "<md width=80>because</md>" in _text(part)


def test_cancelling_an_earlier_question_leaves_the_newer_panel_open(part):
    first = part.begin("first question")
    part.begin("second question")

    part.cancel(first)

    assert part.is_active is True
    assert _text(part).startswith("💭 second question")


def test_cancelling_the_current_question_closes_the_panel(part):
    request = part.begin("why?")

    part.cancel(request)

    assert part.is_active is False
    assert _text(part) == ""


def test_an_answer_arriving_after_esc_is_dropped(part):
    request = part.begin("why?")
    part.dismiss()

    part.end("an answer nobody is waiting for", request)

    assert part.is_active is False
    assert _text(part) == ""


# --- The keys the focused panel receives ------------------------------------
#
# The panel holds the focus while it is shown, so these bindings are what a
# keypress reaches first: the movement keys must walk the answer rather than the
# input's queue recall, and a printable key must still start a message.

LONG_ANSWER = "\n".join(f"line {i}" for i in range(40))


def test_the_answer_arrives_scrolled_to_its_beginning(part):
    part.begin("why?")

    part.end(LONG_ANSWER)

    assert _cursor_row(part) == 0


def test_up_and_down_move_the_answer_one_line_each(part):
    part.begin("why?")
    part.end(LONG_ANSWER)

    for _ in range(3):
        _press(part, "down")
    assert _cursor_row(part) == 3

    _press(part, "up")
    assert _cursor_row(part) == 2


def test_page_up_down_and_home_end_jump_through_the_answer(part):
    part.begin("why?")
    part.end(LONG_ANSWER)
    last_row = _last_row(part)

    _press(part, "pagedown")
    assert _cursor_row(part) == PANEL_PAGE_ROWS

    _press(part, "end")
    assert _cursor_row(part) == last_row

    _press(part, "pageup")
    assert _cursor_row(part) == last_row - PANEL_PAGE_ROWS

    _press(part, "home")
    assert _cursor_row(part) == 0


def test_the_movement_keys_never_start_a_message():
    """A scroll key is not a keystroke's worth of message text."""
    ui = _FakeUI()
    panel = UISideQuestion(ui)
    panel.init_side_question_state()
    panel.begin("why?")
    panel.end(LONG_ANSWER)

    for key in ("down", "pagedown", "end", "up", "pageup", "home"):
        _press(panel, key)

    ui.insert_input_text.assert_not_called()


def test_a_printable_key_starts_a_message_in_the_input():
    """The panel is a read-only answer view, so the character goes to the input."""
    ui = _FakeUI()
    panel = UISideQuestion(ui)
    panel.init_side_question_state()
    panel.begin("why?")
    panel.end(LONG_ANSWER)

    _press(panel, "h")

    ui.insert_input_text.assert_called_once_with("h")
    # The panel still holds the focus, so Up/Down keep scrolling the answer.
    assert panel.is_active is True
    assert LONG_ANSWER in _text(panel)


def test_a_printable_key_leaves_a_selected_passage_alone():
    """Text selected for copying is not typed over."""
    ui = _FakeUI()
    panel = UISideQuestion(ui)
    panel.init_side_question_state()
    panel.begin("why?")
    window = _window(panel)
    window.buffer.start_selection()
    try:
        window.buffer.cursor_position = 3
        _press(panel, "h")
    finally:
        window.buffer.exit_selection()

    ui.insert_input_text.assert_not_called()


def test_escape_closes_the_panel_from_its_own_keys():
    """Esc is bound on the panel too, so it closes whether the key reaches the
    application or the focused widget first."""
    ui = _FakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    part.begin("why?")
    with patch("zrb.llm.ui.default.side_question.focus_widget") as focus:
        _press(part, "escape")

    assert part.is_active is False
    focus.assert_called_once_with(ui.input_field, "Input-field")


def test_the_default_ui_hands_the_focus_to_its_own_panel(mock_ui_deps):
    """The real layout, not a stand-in: the panel lives in a conditional float
    behind a frame, and focusing it has to work through those layers."""
    # lazy: heavy third-party
    from prompt_toolkit.application.current import set_app
    from prompt_toolkit.output import DummyOutput

    from zrb.llm.ui.default.app.focus import focus_widget
    from zrb.llm.ui.default.ui import UI

    ui = UI(**mock_ui_deps)
    with patch(
        "prompt_toolkit.output.create_output", side_effect=lambda **_: DummyOutput()
    ):
        app = ui.application
    with set_app(app), patch(
        "zrb.llm.ui.default.side_question.focus_widget", focus_widget
    ):
        ui.begin_side_question("why is the sky blue?")

        assert app.layout.current_buffer is not ui.input_field.buffer
        assert app.layout.current_buffer.text.startswith("💭 why is the sky blue?")

        ui.dismiss_side_question()

    assert app.layout.current_buffer is ui.input_field.buffer


def test_focus_input_and_scrolling_are_wired_into_one_live_application():
    """The pieces together, through prompt_toolkit's own key dispatch.

    A real input field (whose Up recalls a queued message), the real panel, and
    an application where the panel took the focus from `begin`. Up must move the
    answer and never reach the input's recall; a printable key must land in the
    input while the focus stays put.
    """
    asyncio.run(_drive_live_application())


async def _drive_live_application() -> None:
    # lazy: heavy third-party — the test drives a real prompt_toolkit application
    from prompt_toolkit.application import Application, create_app_session
    from prompt_toolkit.application.current import set_app
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.key_binding import KeyPress
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.layout import HSplit, Layout
    from prompt_toolkit.output import DummyOutput

    # lazy: heavy third-party — the real focus call the panel uses
    from zrb.llm.ui.default.app.focus import focus_widget
    from zrb.llm.ui.default.app.layout import create_input_field

    recalled = MagicMock(name="recalled")
    input_field = create_input_field(
        history_manager=MagicMock(),
        ui_config=MagicMock(),
        up_arrow_handler=lambda event: _recall_queued_message(event, recalled),
        recall_active=lambda: True,
    )
    ui = _FakeUI()
    ui.input_field = input_field
    # The input the panel types into is the one in this application's layout.
    ui.insert_input_text = input_field.buffer.insert_text
    panel = UISideQuestion(ui)
    panel.init_side_question_state()
    window = _window(panel)
    layout = Layout(HSplit([input_field, window]), focused_element=input_field)

    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input, output=DummyOutput()):
            app = Application(layout=layout)
            with set_app(app), patch(
                "zrb.llm.ui.default.side_question.focus_widget", focus_widget
            ):
                panel.begin("why?")
                panel.end(LONG_ANSWER)
                assert app.layout.current_buffer is window.buffer

                app.key_processor.feed(KeyPress(Keys.Down, "\x1b[B"))
                app.key_processor.process_keys()
                assert window.buffer.document.cursor_position_row == 1
                recalled.assert_not_called()
                assert input_field.buffer.text == ""

                app.key_processor.feed(KeyPress("h", "h"))
                app.key_processor.process_keys()
                assert input_field.buffer.text == "h"
                assert app.layout.current_buffer is window.buffer

                # Closing it hands the focus to the input, so the next keystroke
                # is message text rather than a scroll.
                panel.dismiss()
                assert app.layout.current_buffer is input_field.buffer


def _recall_queued_message(event, recalled: MagicMock) -> bool:
    """Stand in for `UIMessageEditing.handle_up_arrow`: load a queued message."""
    recalled(event)
    event.current_buffer.text = "queued message"
    return True
