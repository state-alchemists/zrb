"""create_output_keybindings() wires the output pane's navigation/redirect keys.

Bindings are located by key (rather than driven through a live Application,
which these plain KeyBindings objects aren't attached to) and invoked
directly with a minimal fake event, matching how test_output_scroll.py
exercises the sibling mouse-handler wiring in this same package.
"""

import string
from unittest.mock import MagicMock, patch

from prompt_toolkit.keys import Keys
from prompt_toolkit.widgets import TextArea

from zrb.llm.app.keybinding import create_output_keybindings


def _handler_for(kb, key):
    for binding in kb.bindings:
        if binding.keys == (key,):
            return binding.handler
    raise AssertionError(f"no binding for {key!r}")


def _fake_event(selection_state=None, data=""):
    event = MagicMock()
    event.current_buffer = MagicMock()
    event.current_buffer.selection_state = selection_state
    event.data = data
    event.app.output.get_size.return_value.rows = 24
    return event


def test_binds_escape_up_down_pageup():
    kb = create_output_keybindings(TextArea())
    bound_keys = {binding.keys for binding in kb.bindings}
    assert (Keys.Escape,) in bound_keys
    assert (Keys.Up,) in bound_keys
    assert (Keys.Down,) in bound_keys
    assert (Keys.PageUp,) in bound_keys


def test_binds_every_printable_character_except_control_chars():
    kb = create_output_keybindings(TextArea())
    bound_char_keys = {
        binding.keys[0]
        for binding in kb.bindings
        if isinstance(binding.keys[0], str) and len(binding.keys[0]) == 1
    }
    for char in string.printable:
        if char in "\t\n\r\x0b\x0c":
            assert char not in bound_char_keys
        else:
            assert char in bound_char_keys


def test_escape_focuses_the_input_field():
    input_field = TextArea()

    # get_app is imported inside create_output_keybindings() itself (once,
    # at construction time) — the patch must be active for that call, not
    # just for the later handler invocation, or the closure keeps the real
    # get_app.
    with patch("prompt_toolkit.application.get_app") as mock_get_app:
        kb = create_output_keybindings(input_field)
        handler = _handler_for(kb, Keys.Escape)
        handler(_fake_event())
        mock_get_app.return_value.layout.focus.assert_called_once_with(input_field)


def test_up_moves_cursor_up():
    kb = create_output_keybindings(TextArea())
    handler = _handler_for(kb, Keys.Up)
    event = _fake_event()

    handler(event)

    event.current_buffer.cursor_up.assert_called_once_with()


def test_down_moves_cursor_down():
    kb = create_output_keybindings(TextArea())
    handler = _handler_for(kb, Keys.Down)
    event = _fake_event()

    handler(event)

    event.current_buffer.cursor_down.assert_called_once_with()


def test_pageup_moves_cursor_up_by_screen_height_minus_four():
    kb = create_output_keybindings(TextArea())
    handler = _handler_for(kb, Keys.PageUp)
    event = _fake_event()
    event.app.output.get_size.return_value.rows = 24

    handler(event)

    event.current_buffer.cursor_up.assert_called_once_with(count=20)


def test_printable_char_redirects_focus_and_inserts_when_no_selection():
    # A MagicMock stand-in avoids driving prompt_toolkit's real Buffer.
    # insert_text(), which schedules a background completer task and needs a
    # running event loop this plain unit test doesn't have.
    input_field = MagicMock()
    event = _fake_event(selection_state=None, data="a")

    with patch("prompt_toolkit.application.get_app") as mock_get_app:
        kb = create_output_keybindings(input_field)
        handler = _handler_for(kb, "a")
        handler(event)
        mock_get_app.return_value.layout.focus.assert_called_once_with(input_field)
    input_field.buffer.insert_text.assert_called_once_with("a")


def test_printable_char_does_not_redirect_when_text_is_selected():
    input_field = MagicMock()
    event = _fake_event(selection_state=object(), data="a")

    with patch("prompt_toolkit.application.get_app") as mock_get_app:
        kb = create_output_keybindings(input_field)
        handler = _handler_for(kb, "a")
        handler(event)
        mock_get_app.return_value.layout.focus.assert_not_called()
