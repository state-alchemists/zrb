"""Enter closes the `/btw` panel from the application, not only from the panel.

The panel binds Enter on its own control, which is the case a focused panel
covers. This is the other half: clicking the panel to copy a passage, or a
prompt that already left the focus in the input, keeps the panel up while the
application's Enter binding is what runs. The key that dismisses the panel must
not also send or run the draft typed under it — except over a prompt waiting for
an answer, which Enter still reaches first.
"""

from unittest.mock import MagicMock

import pytest
from prompt_toolkit.key_binding import KeyBindings

from .keybindings_support import MockUI, create_mock_event, trigger_binding


@pytest.fixture
def mock_ui():
    return MockUI()


@pytest.fixture
def setup_bindings(mock_ui):
    key_bindings = KeyBindings()
    mock_ui.setup_app_keybindings(key_bindings, MagicMock())
    return key_bindings


def _with_the_panel_up(mock_ui) -> None:
    mock_ui.is_side_question_active = True
    mock_ui.dismiss_side_question = MagicMock()


def test_enter_closes_an_active_panel_and_sends_nothing(mock_ui, setup_bindings):
    _with_the_panel_up(mock_ui)
    event = create_mock_event("a draft typed under the panel")

    trigger_binding(setup_bindings, "c-m", event)

    mock_ui.dismiss_side_question.assert_called_once_with()
    assert not mock_ui.submit_user_message.called
    assert not event.current_buffer.reset.called


def test_a_command_in_the_draft_waits_for_the_panel_to_close_first(
    mock_ui, setup_bindings
):
    """The panel's own Enter leaves the draft alone, so the app's does too.

    `/btw` runs ahead of a pending approval, so the command check sits before
    `handle_confirmation`; the panel check has to sit before *that* to win, which
    is why it is not simply placed after the confirmation.
    """
    _with_the_panel_up(mock_ui)
    mock_ui.classify_input.return_value = "thinking_command"
    mock_ui.is_thinking = True
    event = create_mock_event("/btw what changed?")

    trigger_binding(setup_bindings, "c-m", event)

    mock_ui.dismiss_side_question.assert_called_once_with()
    assert not mock_ui.schedule_command.called
    assert not event.current_buffer.reset.called


def test_enter_closes_the_panel_while_the_transcript_holds_the_focus(
    mock_ui, setup_bindings
):
    """Enter on the output pane closes the panel; `dismiss` returns the focus."""
    _with_the_panel_up(mock_ui)
    event = create_mock_event("")
    event.app.layout.has_focus = MagicMock(return_value=False)

    trigger_binding(setup_bindings, "c-m", event)

    mock_ui.dismiss_side_question.assert_called_once_with()
    assert not event.app.layout.focus.called
    assert not mock_ui.submit_user_message.called


def test_a_pending_prompt_takes_enter_even_with_the_panel_up(mock_ui, setup_bindings):
    """That field is what the turn is blocked on; the panel takes the next Enter."""
    _with_the_panel_up(mock_ui)
    mock_ui.is_waiting_for_answer = True
    mock_ui.handle_confirmation = MagicMock(return_value=True)
    event = create_mock_event("yes")

    trigger_binding(setup_bindings, "c-m", event)

    assert not mock_ui.dismiss_side_question.called
    assert not mock_ui.submit_user_message.called
