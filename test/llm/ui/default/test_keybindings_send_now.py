"""Ctrl+G sends the queued messages into the running turn."""

from unittest.mock import MagicMock

import pytest
from prompt_toolkit.key_binding import KeyBindings

from zrb.llm.ui.base.queue_delivery import DeliveryOutcome, DeliveryReport
from zrb.llm.ui.default.keybindings import UIKeybindings


class MockUI:
    """Stand-in UI composing the real `UIKeybindings`."""

    def __init__(self):
        self.background_tasks = set()
        self.pending_attachments = []
        self.conversation_session_name = "test_session"
        self.running_llm_task = None
        self.is_thinking = True

        self.input_field = MagicMock()
        self.output_field = MagicMock()
        self.input_field.buffer = MagicMock(text="a draft", cursor_position=7)

        self.outputs = []

        self.send_queued_messages_now = MagicMock(
            return_value=DeliveryReport(DeliveryOutcome.DELIVERED_EARLY, delivered=2)
        )
        self.submit_user_message = MagicMock()
        self.invalidate_ui = MagicMock()

        self._keybindings = UIKeybindings(self)

    def append_to_output(self, text, end="\n"):
        self.outputs.append(str(text) + end)

    def setup_app_keybindings(self, app_keybindings, llm_task):
        return self._keybindings.setup_app_keybindings(app_keybindings, llm_task)


@pytest.fixture
def mock_ui():
    return MockUI()


@pytest.fixture
def setup_bindings(mock_ui):
    key_bindings = KeyBindings()
    mock_ui.setup_app_keybindings(key_bindings, MagicMock())
    return key_bindings


def trigger_binding(key_bindings, key, event):
    """Run the last binding whose filter passes — prompt_toolkit's own key
    processor evaluates `binding.filter()` at match time, and the last match
    wins."""
    bindings = key_bindings.get_bindings_for_keys((key,))
    for binding in reversed(bindings):
        if binding.filter():
            binding.handler(event)
            return True
    return False


def create_mock_event():
    event = MagicMock()
    event.app.layout.has_focus = MagicMock(return_value=True)
    event.current_buffer.text = "a draft"
    event.current_buffer.reset = MagicMock()
    return event


def test_ctrl_g_is_bound(mock_ui, setup_bindings):
    assert setup_bindings.get_bindings_for_keys(("c-g",))


def test_ctrl_g_sends_the_queued_messages(mock_ui, setup_bindings):
    trigger_binding(setup_bindings, "c-g", create_mock_event())

    mock_ui.send_queued_messages_now.assert_called_once_with()


def test_ctrl_g_says_what_happened(mock_ui, setup_bindings):
    trigger_binding(setup_bindings, "c-g", create_mock_event())

    assert "sent 2 queued message(s)" in "".join(mock_ui.outputs)


def test_ctrl_g_leaves_the_draft_alone(mock_ui, setup_bindings):
    event = create_mock_event()

    trigger_binding(setup_bindings, "c-g", event)

    # Ctrl+G is not a submit: the draft stays in the input box.
    assert not mock_ui.submit_user_message.called
    assert not event.current_buffer.reset.called
    assert mock_ui.input_field.buffer.text == "a draft"


def test_ctrl_g_refreshes_the_screen(mock_ui, setup_bindings):
    trigger_binding(setup_bindings, "c-g", create_mock_event())

    mock_ui.invalidate_ui.assert_called_once_with()
