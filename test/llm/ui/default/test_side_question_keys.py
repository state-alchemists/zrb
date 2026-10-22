"""The keys the focused `/btw` panel receives.

While the panel holds the focus, the movement keys must scroll the answer rather
than reach the input's queue recall, and a typed character must still start a
message. The application bit that forwards typing is driven through
prompt_toolkit's own dispatch too, so the ordering against Enter and the other
application bindings is asserted, not just the binding table.
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
    """The tests that care which widget the focus names patch the seam."""
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


def _press(part: UISideQuestion, key: str, data: str | None = None) -> None:
    """Deliver *key* the way the running application does.

    The panel holds the focus while it is shown, so its own control bindings
    answer the keypress; the last matching binding wins, as in prompt_toolkit.
    *data* is what the key carries — `\\x1b[B` for Down, the character itself for
    a letter — and defaults to the key's own name.
    """
    window = _window(part)
    event = MagicMock(name="event")
    event.data = key if data is None else data
    event.current_buffer = window.buffer
    for binding in reversed(window.control.key_bindings.get_bindings_for_keys((key,))):
        if binding.filter():
            binding.handler(event)
            return
    raise AssertionError(f"the panel binds no {key!r}")


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


def _type(part: UISideQuestion, text: str) -> None:
    """Deliver *text* the way the application-level catch-all does.

    The panel binds no characters, so a typed character reaches the input
    through `handle_typed_text` rather than a binding on the panel.
    """
    part.handle_typed_text(text)


def test_a_printable_key_starts_a_message_in_the_input():
    """The panel is a read-only answer view, so the character goes to the input."""
    ui = _FakeUI()
    panel = UISideQuestion(ui)
    panel.init_side_question_state()
    panel.begin("why?")
    panel.end(LONG_ANSWER)

    _type(panel, "h")

    ui.insert_input_text.assert_called_once_with("h")
    # The panel still holds the focus, so Up/Down keep scrolling the answer.
    assert panel.is_active is True
    assert LONG_ANSWER in _text(panel)


def _asking_panel():
    """A panel showing the answer to "why?", plus the UI it types into."""
    ui = _FakeUI()
    panel = UISideQuestion(ui)
    panel.init_side_question_state()
    panel.begin("why?")
    return ui, panel


@pytest.mark.parametrize("key", ["é", "ü", "🙂"])
def test_a_non_ascii_key_starts_a_message_too(key):
    """Self-insert delivers the character, not an ASCII-only binding table."""
    ui, panel = _asking_panel()

    _type(panel, key)

    ui.insert_input_text.assert_called_once_with(key)
    assert panel.is_active is True


def test_a_control_key_is_not_message_text():
    """Ctrl+A carries a control character, not the character it stands for."""
    ui, panel = _asking_panel()

    _type(panel, "\x01")

    ui.insert_input_text.assert_not_called()


def test_the_down_escape_sequence_scrolls_and_types_nothing():
    """Down arrives as `\\x1b[B`: the panel's own binding takes it."""
    ui, panel = _asking_panel()
    panel.end(LONG_ANSWER)

    _press(panel, "down", "\x1b[B")

    assert _cursor_row(panel) == 1
    ui.insert_input_text.assert_not_called()


def test_the_panel_binds_no_catch_all_so_application_keys_stay_free():
    """A `Keys.Any` binding would answer Enter, Ctrl+X and Ctrl+G before the
    application's own handlers; the panel must leave them unbound."""
    _, panel = _asking_panel()
    bindings = _window(panel).control.key_bindings

    for key in ("enter", "c-x", "c-g"):
        assert bindings.get_bindings_for_keys((key,)) == []


def test_a_paste_reaches_the_input_whole():
    """A paste, or a dead-key sequence, is one data string — not a keypress each."""
    ui, panel = _asking_panel()

    _type(panel, "héllo 🙂")

    ui.insert_input_text.assert_called_once_with("héllo 🙂")


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
        panel.handle_typed_text("h")
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
    from prompt_toolkit.key_binding import KeyBindings, KeyPress
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
    app_keybindings = KeyBindings()
    handled = MagicMock(name="handled")

    @app_keybindings.add("enter")
    def _(event):
        handled("enter")
        event.app.layout.focus(input_field)

    @app_keybindings.add("c-g")
    def _(event):
        handled("c-g")

    ui = _FakeUI()
    ui.input_field = input_field
    # The input the panel types into is the one in this application's layout.
    ui.insert_input_text = input_field.buffer.insert_text
    panel = UISideQuestion(ui)
    panel.init_side_question_state()
    window = _window(panel)

    # The product's application-level catch-all while the panel is focused.
    @app_keybindings.add(Keys.Any)
    def _(event):
        panel.handle_typed_text(event.data)

    layout = Layout(HSplit([input_field, window]), focused_element=input_field)

    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input, output=DummyOutput()):
            app = Application(layout=layout, key_bindings=app_keybindings)
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

                # A character outside ASCII reaches the same self-insert path.
                for key in ("é", "🙂"):
                    app.key_processor.feed(KeyPress(key, key))
                    app.key_processor.process_keys()
                assert input_field.buffer.text == "hé🙂"

                # Keys the panel does not bind reach the application's handlers.
                app.key_processor.feed(KeyPress(Keys.ControlG, "\x07"))
                app.key_processor.process_keys()
                handled.assert_called_once_with("c-g")
                assert app.layout.current_buffer is window.buffer

                app.key_processor.feed(KeyPress(Keys.Enter, "\r"))
                app.key_processor.process_keys()
                handled.assert_called_with("enter")
                assert app.layout.current_buffer is input_field.buffer


def _recall_queued_message(event, recalled: MagicMock) -> bool:
    """Stand in for `UIMessageEditing.handle_up_arrow`: load a queued message."""
    recalled(event)
    event.current_buffer.text = "queued message"
    return True
