from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.clipboard import ClipboardData
from prompt_toolkit.key_binding import KeyBindings

from zrb.llm.hook.interface import HookEvent
from zrb.llm.ui.base.message_queue import MessageQueue
from zrb.llm.ui.default.agent_picker import UIAgentPicker
from zrb.llm.ui.default.keybindings import UIKeybindings
from zrb.llm.ui.default.message_editing import UIMessageEditing


class MockUI:
    """Stand-in UI composing the real `UIKeybindings`, `UIMessageEditing`
    and `UIAgentPicker`. Each part reaches this object's state via
    `self._ui`, using only public names — matching the real default `UI`.
    State that lives inside the composed parts themselves (`queued_edit_entry`/
    `queued_edit_draft` on `UIMessageEditing`, `viewing_agent_id`/
    `saved_main_output` on `UIAgentPicker`) is reached the same way tests reach
    it: through the part's own public property, via `__getattr__` below.
    """

    def __init__(self):
        self.background_tasks = set()
        self.pending_attachments = []
        self.conversation_session_name = "test_session"
        self.running_llm_task = None
        self.is_thinking = False
        self.voice_mode_active = False
        self.voice_recording_active = False
        self.voice_task = None
        self.voice_stop_event = None

        self.input_field = MagicMock()
        self.output_field = MagicMock()
        self.input_field.buffer = MagicMock(text="", cursor_position=0)

        self.outputs = []

        self._message_queue = MessageQueue()
        self.edit_queued_message = MagicMock(return_value=True)

        self._keybindings = UIKeybindings(self)
        self._message_editing = UIMessageEditing(self)
        # Sub-agent picker + live view (see UIAgentPicker). Mirrors the real
        # default `UI` composition so Down Arrow's picker trigger works.
        self._agent_picker = UIAgentPicker(self)
        self._agent_picker.init_agent_picker_state()

        # Mocks for BaseUI methods
        self.cancel_pending_confirmations = MagicMock()
        self.execute_hook = MagicMock()
        self.append_to_output = MagicMock(side_effect=lambda x: self.outputs.append(x))
        self.invalidate_ui = MagicMock()
        self.toggle_yolo = MagicMock()
        self.toggle_collapsible_block = MagicMock()
        self.cycle_mode = MagicMock()
        self.submit_user_message = MagicMock()
        self.schedule_command = MagicMock()
        self.classify_input = MagicMock(return_value="message")

        # Mocks for BaseUICommands methods
        self._handle_btw_command = MagicMock(return_value=False)
        self._handle_toggle_yolo = MagicMock(return_value=False)
        self._handle_exit_command = MagicMock(return_value=False)
        self._handle_info_command = MagicMock(return_value=False)
        self._handle_save_command = MagicMock(return_value=False)
        self._handle_load_command = MagicMock(return_value=False)
        self._handle_rewind_command = MagicMock(return_value=False)
        self._handle_redirect_command = MagicMock(return_value=False)
        self._handle_attach_command = MagicMock(return_value=False)
        self._handle_set_model_command = MagicMock(return_value=False)
        self._handle_exec_command = MagicMock(return_value=False)
        self._handle_custom_command = MagicMock(return_value=False)

        # Mock for confirmation handling
        self.handle_confirmation = MagicMock(return_value=False)

    @property
    def effective_message_queue(self):
        return self._message_queue

    @property
    def output_text(self):
        return self.output_field.text

    def set_output_text(self, text):
        self.output_field.text = text

    def setup_app_keybindings(self, app_keybindings, llm_task):
        return self._keybindings.setup_app_keybindings(app_keybindings, llm_task)

    # `__getattr__` below handles reads of state that lives on a composed
    # part, but not writes (Python's default `__setattr__` would just shadow
    # it with a same-named instance attribute on this mock instead). These
    # forward both directions, through the part's own public property.

    @property
    def queued_edit_entry(self):
        return self._message_editing.queued_edit_entry

    @queued_edit_entry.setter
    def queued_edit_entry(self, value):
        self._message_editing.queued_edit_entry = value

    @property
    def queued_edit_draft(self):
        return self._message_editing.queued_edit_draft

    @queued_edit_draft.setter
    def queued_edit_draft(self, value):
        self._message_editing.queued_edit_draft = value

    @property
    def viewing_agent_id(self):
        return self._agent_picker.viewing_agent_id

    @viewing_agent_id.setter
    def viewing_agent_id(self, value):
        self._agent_picker.viewing_agent_id = value

    @property
    def saved_main_output(self):
        return self._agent_picker.saved_main_output

    @saved_main_output.setter
    def saved_main_output(self, value):
        self._agent_picker.saved_main_output = value

    def __getattr__(self, name):
        for part_attr in ("_message_editing", "_agent_picker", "_keybindings"):
            part = self.__dict__.get(part_attr)
            if part is not None and hasattr(part, name):
                return getattr(part, name)
        raise AttributeError(name)


@pytest.fixture
def mock_ui():
    return MockUI()


@pytest.fixture
def key_bindings():
    return KeyBindings()


@pytest.fixture
def setup_bindings(mock_ui, key_bindings):
    llm_task = MagicMock()
    mock_ui.setup_app_keybindings(key_bindings, llm_task)
    return key_bindings


def create_mock_event(text=""):
    event = MagicMock()
    event.app.layout.has_focus = MagicMock(return_value=True)
    event.app.layout.focus = MagicMock()

    event.app.current_buffer.text = text
    event.app.current_buffer.selection_state = None
    event.app.current_buffer.copy_selection = MagicMock(
        return_value=ClipboardData("copied_text")
    )
    event.app.current_buffer.exit_selection = MagicMock()
    event.app.current_buffer.reset = MagicMock()
    event.app.current_buffer.append_to_history = MagicMock()
    event.app.current_buffer.insert_text = MagicMock()
    event.app.current_buffer.delete_before_cursor = MagicMock()
    event.app.current_buffer.cursor_position = len(text)

    event.current_buffer = event.app.current_buffer

    event.app.clipboard = MagicMock()
    event.app.clipboard.set_data = MagicMock()
    event.app.clipboard.get_data = MagicMock(return_value="pasted_text")

    event.app.exit = MagicMock()
    return event


def trigger_binding(key_bindings, key, event):
    bindings = key_bindings.get_bindings_for_keys((key,))
    if not bindings:
        return False
    # Execute the last binding whose filter passes — prompt_toolkit's own
    # key processor (its match-finding step) evaluates `binding.filter()` at
    # match time even though the raw registry's `get_bindings_for_keys`
    # returns inactive bindings too. Last-match-wins mirrors prompt_toolkit's
    # priority order.
    for binding in reversed(bindings):
        if binding.filter():
            binding.handler(event)
            return True
    return False


class _FakeLiveRegistry:
    def __init__(self, cancel_result=True):
        self.sent = []
        self.cancelled = []
        self.cancel_result = cancel_result
        self.entry = MagicMock()

    async def send_message(self, session_id, agent_id, text):
        self.sent.append((session_id, agent_id, text))
        return True

    def get(self, session_id, agent_id):
        return self.entry

    def cancel(self, session_id, agent_id):
        self.cancelled.append((session_id, agent_id))
        return self.cancel_result


def test_ctrl_k_binding_focus_output(mock_ui, setup_bindings):
    """Ctrl+K toggles focus to the output pane when input has focus."""
    event = create_mock_event()
    event.app.layout.has_focus.return_value = True
    trigger_binding(setup_bindings, "c-k", event)
    event.app.layout.focus.assert_called_with(mock_ui.output_field)


def test_ctrl_k_binding_focus_input(mock_ui, setup_bindings):
    event = create_mock_event()
    event.app.layout.has_focus.return_value = False
    trigger_binding(setup_bindings, "c-k", event)
    event.app.layout.focus.assert_called_with(mock_ui.input_field)


def test_tab_does_not_cycle_mode_off_termux(mock_ui, setup_bindings):
    """Off Termux, plain Tab is unbound and does not cycle the mode.

    Only Shift+Tab cycles; Tab is left free for its default behavior.
    prompt_toolkit normalizes ``"tab"`` to ``Keys.ControlI`` (``c-i``).
    """
    event = create_mock_event()
    triggered = trigger_binding(setup_bindings, "c-i", event)
    assert triggered is False
    mock_ui.cycle_mode.assert_not_called()


def test_tab_cycles_mode_on_termux(mock_ui, key_bindings, monkeypatch):
    """On Termux, Shift+Tab is indistinguishable from Tab, so plain Tab
    (``c-i``) is bound to mode cycling as a fallback."""
    monkeypatch.setenv("ZRB_IS_TERMUX", "true")
    mock_ui.setup_app_keybindings(key_bindings, MagicMock())
    event = create_mock_event()
    trigger_binding(key_bindings, "c-i", event)
    mock_ui.cycle_mode.assert_called_once()


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
    event = create_mock_event("some text")
    trigger_binding(setup_bindings, "c-c", event)
    event.app.current_buffer.reset.assert_called_once()
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


def test_escape_binding(mock_ui, setup_bindings):
    event = create_mock_event()

    # Setup running task
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_ui.running_llm_task = mock_task

    trigger_binding(setup_bindings, "escape", event)

    mock_ui.cancel_pending_confirmations.assert_called_once()
    mock_task.cancel.assert_called_once()
    mock_ui.execute_hook.assert_called_with(
        HookEvent.STOP,
        {"reason": "escape", "session": "test_session"},
    )
    assert "\n<Esc> Canceled" in mock_ui.outputs


def test_escape_while_viewing_sub_agent_cancels_it(mock_ui, setup_bindings):
    # Esc while the output pane shows a sub-agent cancels what that sub-agent
    # is doing (mirroring the main agent's Esc) — it never leaves the view
    # (Left does), never cancels the running main task, and never fires the
    # main STOP hook.
    event = create_mock_event()
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_ui.running_llm_task = mock_task
    mock_ui.output_field.text = "sub-agent live output"
    mock_ui.viewing_agent_id = "abc123"
    mock_ui.saved_main_output = "main transcript"
    fake = _FakeLiveRegistry()

    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry", fake
    ):
        trigger_binding(setup_bindings, "escape", event)

    assert fake.cancelled == [("test_session", "abc123")]
    mock_ui.cancel_pending_confirmations.assert_called_once()
    mock_task.cancel.assert_not_called()  # never the main task
    mock_ui.execute_hook.assert_not_called()
    assert mock_ui.viewing_agent_id == "abc123"  # still in the view
    assert mock_ui.saved_main_output == "main transcript"


def test_escape_while_viewing_idle_sub_agent_does_nothing(mock_ui, setup_bindings):
    # Esc against an idle sub-agent (nothing in flight) has nothing to cancel
    # — no echo, no view change, no main-task involvement.
    event = create_mock_event()
    mock_ui.viewing_agent_id = "abc123"
    mock_ui.saved_main_output = "main transcript"
    fake = _FakeLiveRegistry(cancel_result=False)

    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry", fake
    ):
        trigger_binding(setup_bindings, "escape", event)

    assert fake.cancelled == [("test_session", "abc123")]
    assert mock_ui.viewing_agent_id == "abc123"
    assert "\n<Esc> Canceled\n" not in "".join(mock_ui.outputs)


def test_left_arrow_while_viewing_returns_to_parent(mock_ui, setup_bindings):
    # Left while the output pane shows a sub-agent returns to the main session
    # (navigation only — the sub-agent's work is untouched).
    event = create_mock_event()
    mock_ui.output_field.text = "sub-agent live output"
    mock_ui.viewing_agent_id = "abc123"
    mock_ui.saved_main_output = "main transcript"

    triggered = trigger_binding(setup_bindings, "left", event)

    assert triggered is True
    assert mock_ui.viewing_agent_id is None
    assert mock_ui.saved_main_output is None
    assert mock_ui.output_text == "main transcript"  # parked transcript restored


def test_left_arrow_not_bound_while_not_viewing(mock_ui, setup_bindings):
    # The Left binding is filtered to the sub-agent view; everywhere else it
    # stays free for cursor movement.
    event = create_mock_event()
    assert trigger_binding(setup_bindings, "left", event) is False


def test_ctrl_y_binding(mock_ui, setup_bindings):
    event = create_mock_event()
    trigger_binding(setup_bindings, "c-y", event)
    mock_ui.toggle_yolo.assert_called_once()


def test_ctrl_o_binding(mock_ui, setup_bindings):
    event = create_mock_event()
    trigger_binding(setup_bindings, "c-o", event)
    mock_ui.toggle_collapsible_block.assert_called_once()


def test_ctrl_o_binding_fires_while_viewing_sub_agent(mock_ui, setup_bindings):
    """Unlike `left`, Ctrl+O is unconditional: `ui.toggle_collapsible_block`
    itself routes to the viewed sub-agent's own toggle-block scope when
    `viewing_agent_id` is set, so the binding stays correct in both states —
    tested separately at the `UI`/`UIAgentPicker` level."""
    event = create_mock_event()
    mock_ui.viewing_agent_id = "abc123"

    triggered = trigger_binding(setup_bindings, "c-o", event)

    assert triggered is True
    mock_ui.toggle_collapsible_block.assert_called_once()


def test_shift_tab_cycles_mode(mock_ui, setup_bindings):
    event = create_mock_event()
    trigger_binding(setup_bindings, "s-tab", event)
    mock_ui.cycle_mode.assert_called_once()


def test_ctrl_j_binding(mock_ui, setup_bindings):
    event = create_mock_event()
    trigger_binding(setup_bindings, "c-j", event)
    event.current_buffer.insert_text.assert_called_with("\n")


def test_enter_empty_text(mock_ui, setup_bindings):
    event = create_mock_event("   ")
    trigger_binding(setup_bindings, "c-m", event)
    assert not mock_ui.submit_user_message.called


def test_enter_handle_multiline(mock_ui, setup_bindings):
    event = create_mock_event("line1\\")
    trigger_binding(setup_bindings, "c-m", event)
    event.current_buffer.delete_before_cursor.assert_called_with(count=1)
    event.current_buffer.insert_text.assert_called_with("\n")
    assert not mock_ui.submit_user_message.called


def test_enter_handle_confirmation(mock_ui, setup_bindings):
    event = create_mock_event("yes")
    mock_ui.handle_confirmation.return_value = True
    trigger_binding(setup_bindings, "c-m", event)
    assert not mock_ui.submit_user_message.called


def test_enter_thinking_command_routes_even_while_thinking(mock_ui, setup_bindings):
    # Run-while-thinking commands (/btw, YOLO toggle) dispatch regardless of
    # the thinking state. Commands are not appended to input history (main
    # never recalled recognized commands).
    event = create_mock_event("/btw hello")
    mock_ui.classify_input.return_value = "thinking_command"
    mock_ui.is_thinking = True
    trigger_binding(setup_bindings, "c-m", event)
    # Scheduled unguarded so it never blocks / is blocked by another command.
    mock_ui.schedule_command.assert_called_once_with("/btw hello", guarded=False)
    event.current_buffer.reset.assert_called_once()
    assert not event.current_buffer.append_to_history.called
    assert not mock_ui.submit_user_message.called
