"""Ctrl+C / Ctrl+D — copy the selection, clear the draft, or exit.

Both read the input field rather than whichever pane has focus: the output
pane is `focus_on_click`, so a click on the transcript puts it in
`current_buffer` and the press would read as "there is text, clear it".
"""

from unittest.mock import MagicMock

from zrb.llm.hook.interface import HookEvent

from .test_keybindings_focus import (  # noqa: F401  (fixtures)
    MockUI,
    create_mock_event,
    key_bindings,
    mock_ui,
    setup_bindings,
    trigger_binding,
)


def test_ctrl_c_selection(mock_ui, setup_bindings):
    event = create_mock_event()
    event.app.current_buffer.selection_state = True
    trigger_binding(setup_bindings, "c-c", event)
    event.app.current_buffer.exit_selection.assert_called_once()
    assert not mock_ui.cancel_pending_confirmations.called
    # Clipboard receives the ClipboardData with ANSI styling stripped from text.
    event.app.clipboard.set_data.assert_called_once()
    (sent_data,) = event.app.clipboard.set_data.call_args.args
    assert sent_data.text == "copied_text"


def test_ctrl_c_text_present(mock_ui, setup_bindings):
    event = create_mock_event()
    mock_ui.input_field.buffer.text = "some text"
    trigger_binding(setup_bindings, "c-c", event)
    mock_ui.input_field.buffer.reset.assert_called_once()
    assert not mock_ui.cancel_pending_confirmations.called


def test_ctrl_c_empty(mock_ui, setup_bindings):
    event = create_mock_event("")

    # Setup running task
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_ui.running_llm_task = mock_task

    trigger_binding(setup_bindings, "c-c", event)

    mock_ui.cancel_pending_confirmations.assert_called_once()
    mock_task.cancel.assert_called_once()
    assert "\n<Esc> Canceled" in mock_ui.outputs
    mock_ui.execute_hook.assert_called_with(
        HookEvent.STOP,
        {"reason": "ctrl_c", "session": "test_session"},
    )
    event.app.exit.assert_called_once()


def test_ctrl_c_quits_when_the_output_pane_has_focus(mock_ui, setup_bindings):
    event = create_mock_event("a long transcript\n")
    event.app.layout.has_focus = MagicMock(return_value=False)

    trigger_binding(setup_bindings, "c-c", event)

    event.app.exit.assert_called_once()
    mock_ui.cancel_pending_confirmations.assert_called_once()
    event.app.current_buffer.reset.assert_not_called()


def test_ctrl_c_clears_the_draft_under_output_focus(mock_ui, setup_bindings):
    event = create_mock_event("a long transcript\n")
    event.app.layout.has_focus = MagicMock(return_value=False)
    mock_ui.input_field.buffer.text = "half a thought"

    trigger_binding(setup_bindings, "c-c", event)

    mock_ui.input_field.buffer.reset.assert_called_once()
    event.app.exit.assert_not_called()


def test_ctrl_d_quits_when_the_output_pane_has_focus(mock_ui, setup_bindings):
    event = create_mock_event("a long transcript\n")
    event.app.layout.has_focus = MagicMock(return_value=False)

    trigger_binding(setup_bindings, "c-d", event)

    event.app.exit.assert_called_once()
