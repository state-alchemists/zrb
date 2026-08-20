import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prompt_toolkit.clipboard import ClipboardData
from prompt_toolkit.key_binding import KeyBindings

from zrb.llm.hook.interface import HookEvent
from zrb.llm.ui.base.message_queue import MessageQueue, QueuedMessage
from zrb.llm.ui.default.agent_picker import UIAgentPicker
from zrb.llm.ui.default.keybindings import UIKeybindings
from zrb.llm.ui.default.message_editing import UIMessageEditing


class MockUI:
    """Stand-in UI composing the real `UIKeybindings`, `UIMessageEditing`
    and `UIAgentPicker`. Each part reaches this object's state via
    `self._ui`, so most of the state below is unchanged from the old
    inheritance-based test double. The exception is state that now lives
    *inside* the composed parts themselves (`_queued_edit_entry`/
    `_queued_edit_draft` on `UIMessageEditing`, `_viewing_agent_id`/
    `_saved_main_output` on `UIAgentPicker`) — a handful of tests poke those
    directly, so this class exposes them as properties forwarding to the
    real owning part.
    """

    def __init__(self):
        self._background_tasks = set()
        self._pending_attachments = []
        self._conversation_session_name = "test_session"
        self._running_llm_task = None
        self._is_thinking = False
        self._voice_mode_active = False
        self._voice_recording_active = False
        self._voice_task = None
        self._voice_stop_event = None

        self._input_field = MagicMock()
        self._output_field = MagicMock()
        self._input_field.buffer = MagicMock(text="", cursor_position=0)

        self.outputs = []

        self._message_queue = MessageQueue()
        self.edit_queued_message = MagicMock(return_value=True)

        self._keybindings = UIKeybindings(self)
        self._message_editing = UIMessageEditing(self)
        # Sub-agent picker + live view (see UIAgentPicker). Mirrors the real
        # default `UI` composition so Down Arrow's picker trigger works.
        self._agent_picker = UIAgentPicker(self)
        self._agent_picker._init_agent_picker_state()

        # Mocks for BaseUI methods
        self._cancel_pending_confirmations = MagicMock()
        self.execute_hook = MagicMock()
        self.append_to_output = MagicMock(side_effect=lambda x: self.outputs.append(x))
        self.invalidate_ui = MagicMock()
        self.toggle_yolo = MagicMock()
        self.cycle_mode = MagicMock()
        self._submit_user_message = MagicMock()
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
        self._handle_confirmation = MagicMock(return_value=False)

    @property
    def effective_message_queue(self):
        return self._message_queue

    @property
    def output_text(self):
        return self._output_field.text

    def _set_output_text(self, text):
        self._output_field.text = text

    def setup_app_keybindings(self, app_keybindings, llm_task):
        return self._keybindings.setup_app_keybindings(app_keybindings, llm_task)

    @property
    def _queued_edit_entry(self):
        return self._message_editing._queued_edit_entry

    @_queued_edit_entry.setter
    def _queued_edit_entry(self, value):
        self._message_editing._queued_edit_entry = value

    @property
    def _queued_edit_draft(self):
        return self._message_editing._queued_edit_draft

    @_queued_edit_draft.setter
    def _queued_edit_draft(self, value):
        self._message_editing._queued_edit_draft = value

    @property
    def _viewing_agent_id(self):
        return self._agent_picker._viewing_agent_id

    @_viewing_agent_id.setter
    def _viewing_agent_id(self, value):
        self._agent_picker._viewing_agent_id = value

    @property
    def _saved_main_output(self):
        return self._agent_picker._saved_main_output

    @_saved_main_output.setter
    def _saved_main_output(self, value):
        self._agent_picker._saved_main_output = value

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
    # Execute the last binding whose filter passes — the KeyProcessor
    # (`KeyProcessor._get_matches`) evaluates `binding.filter()` at match time
    # even though the raw registry's `get_bindings_for_keys` returns inactive
    # bindings too. Last-match-wins mirrors prompt_toolkit's priority order.
    for binding in reversed(bindings):
        if binding.filter():
            binding.handler(event)
            return True
    return False


def test_ctrl_k_binding_focus_output(mock_ui, setup_bindings):
    """Ctrl+K toggles focus to the output pane when input has focus."""
    event = create_mock_event()
    event.app.layout.has_focus.return_value = True
    trigger_binding(setup_bindings, "c-k", event)
    event.app.layout.focus.assert_called_with(mock_ui._output_field)


def test_ctrl_k_binding_focus_input(mock_ui, setup_bindings):
    event = create_mock_event()
    event.app.layout.has_focus.return_value = False
    trigger_binding(setup_bindings, "c-k", event)
    event.app.layout.focus.assert_called_with(mock_ui._input_field)


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
    assert not mock_ui._cancel_pending_confirmations.called
    # Clipboard receives the ClipboardData with ANSI styling stripped from text.
    event.app.clipboard.set_data.assert_called_once()
    (sent_data,) = event.app.clipboard.set_data.call_args.args
    assert sent_data.text == "copied_text"


def test_ctrl_c_text_present(mock_ui, setup_bindings):
    event = create_mock_event("some text")
    trigger_binding(setup_bindings, "c-c", event)
    event.app.current_buffer.reset.assert_called_once()
    assert not mock_ui._cancel_pending_confirmations.called


def test_ctrl_c_empty(mock_ui, setup_bindings):
    event = create_mock_event("")

    # Setup running task
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_ui._running_llm_task = mock_task

    trigger_binding(setup_bindings, "c-c", event)

    mock_ui._cancel_pending_confirmations.assert_called_once()
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
    mock_ui._running_llm_task = mock_task

    trigger_binding(setup_bindings, "escape", event)

    mock_ui._cancel_pending_confirmations.assert_called_once()
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
    mock_ui._running_llm_task = mock_task
    mock_ui._output_field.text = "sub-agent live output"
    mock_ui._viewing_agent_id = "abc123"
    mock_ui._saved_main_output = "main transcript"
    fake = _FakeLiveRegistry()

    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry", fake
    ):
        trigger_binding(setup_bindings, "escape", event)

    assert fake.cancelled == [("test_session", "abc123")]
    mock_ui._cancel_pending_confirmations.assert_called_once()
    mock_task.cancel.assert_not_called()  # never the main task
    mock_ui.execute_hook.assert_not_called()
    assert mock_ui.viewing_agent_id == "abc123"  # still in the view
    assert mock_ui.saved_main_output == "main transcript"


def test_escape_while_viewing_idle_sub_agent_does_nothing(mock_ui, setup_bindings):
    # Esc against an idle sub-agent (nothing in flight) has nothing to cancel
    # — no echo, no view change, no main-task involvement.
    event = create_mock_event()
    mock_ui._viewing_agent_id = "abc123"
    mock_ui._saved_main_output = "main transcript"
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
    mock_ui._output_field.text = "sub-agent live output"
    mock_ui._viewing_agent_id = "abc123"
    mock_ui._saved_main_output = "main transcript"

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
    assert not mock_ui._submit_user_message.called


def test_enter_handle_multiline(mock_ui, setup_bindings):
    event = create_mock_event("line1\\")
    trigger_binding(setup_bindings, "c-m", event)
    event.current_buffer.delete_before_cursor.assert_called_with(count=1)
    event.current_buffer.insert_text.assert_called_with("\n")
    assert not mock_ui._submit_user_message.called


def test_enter_handle_confirmation(mock_ui, setup_bindings):
    event = create_mock_event("yes")
    mock_ui._handle_confirmation.return_value = True
    trigger_binding(setup_bindings, "c-m", event)
    assert not mock_ui._submit_user_message.called


def test_enter_thinking_command_routes_even_while_thinking(mock_ui, setup_bindings):
    # Run-while-thinking commands (/btw, YOLO toggle) dispatch regardless of
    # the thinking state. Commands are not appended to input history (main
    # never recalled recognized commands).
    event = create_mock_event("/btw hello")
    mock_ui.classify_input.return_value = "thinking_command"
    mock_ui._is_thinking = True
    trigger_binding(setup_bindings, "c-m", event)
    # Scheduled unguarded so it never blocks / is blocked by another command.
    mock_ui.schedule_command.assert_called_once_with("/btw hello", guarded=False)
    event.current_buffer.reset.assert_called_once()
    assert not event.current_buffer.append_to_history.called
    assert not mock_ui._submit_user_message.called


def test_enter_command_routes_to_dispatch(mock_ui, setup_bindings):
    # A recognized command (any token, e.g. ">" redirect) goes through the
    # hook-wrapped async dispatch — never submitted to the LLM directly.
    # Guards the regression where ">" redirect was swallowed.
    event = create_mock_event("> ~/coba.txt")
    mock_ui.classify_input.return_value = "command"
    trigger_binding(setup_bindings, "c-m", event)
    mock_ui.schedule_command.assert_called_once_with("> ~/coba.txt")
    event.current_buffer.reset.assert_called_once()
    assert not mock_ui._submit_user_message.called


def test_enter_command_gated_while_thinking(mock_ui, setup_bindings):
    # A non-thinking command typed while the LLM is responding is held (not
    # dispatched, not submitted, buffer kept) — matches main.
    event = create_mock_event("/save x")
    mock_ui.classify_input.return_value = "command"
    mock_ui._is_thinking = True
    trigger_binding(setup_bindings, "c-m", event)
    assert not mock_ui.schedule_command.called
    assert not mock_ui._submit_user_message.called
    assert not event.current_buffer.reset.called


def test_enter_message_while_thinking_is_queued(mock_ui, setup_bindings):
    # Typing while the assistant works queues the message (the message loop runs
    # one job at a time) instead of swallowing the Enter.
    event = create_mock_event("hello")
    mock_ui.classify_input.return_value = "message"
    mock_ui._is_thinking = True
    trigger_binding(setup_bindings, "c-m", event)
    mock_ui._submit_user_message.assert_called_once()
    event.current_buffer.reset.assert_called_once()
    assert not mock_ui.schedule_command.called


# ── Live sub-agent view (Enter routes to the viewed sub-agent) ────────────


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


@pytest.mark.asyncio
async def test_enter_while_viewing_sends_message_to_sub_agent(mock_ui, setup_bindings):
    event = create_mock_event("hello sub-agent")
    mock_ui._viewing_agent_id = "abc123"
    fake = _FakeLiveRegistry()

    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry", fake
    ):
        trigger_binding(setup_bindings, "c-m", event)
        for task in list(mock_ui._background_tasks):
            await task
        assert fake.sent == [("test_session", "abc123", "hello sub-agent")]
        event.current_buffer.reset.assert_called_once()
        # The message is echoed into the sub-agent's own buffer so its live
        # view reads as a conversation.
        fake.entry.buffered_ui.append_to_output.assert_called_once_with(
            "\n💬 hello sub-agent\n"
        )
        assert not mock_ui._submit_user_message.called
        assert not mock_ui.schedule_command.called
        assert not mock_ui.classify_input.called


@pytest.mark.asyncio
async def test_enter_while_viewing_sends_slash_command_as_message(
    mock_ui, setup_bindings
):
    # While viewing, even a "/..." line goes to the sub-agent as a plain
    # message — it must never dispatch as a main-session command.
    event = create_mock_event("/save x")
    mock_ui._viewing_agent_id = "abc123"
    fake = _FakeLiveRegistry()

    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry", fake
    ):
        trigger_binding(setup_bindings, "c-m", event)
        for task in list(mock_ui._background_tasks):
            await task
        assert fake.sent == [("test_session", "abc123", "/save x")]

    assert not mock_ui.schedule_command.called
    assert not mock_ui._submit_user_message.called


# ── Queued-message editing (UIMessageEditing) ────────────────────────────


def _queued_entry(text, kind="message"):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind=kind, run=run)


def test_up_arrow_recalls_queued_message(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui._message_queue.put_nowait(entry)
    event = create_mock_event("current draft")

    assert mock_ui._handle_up_arrow(event) is True
    assert event.current_buffer.text == "queued message"
    assert event.current_buffer.cursor_position == len("queued message")
    assert mock_ui.queued_edit_entry is entry
    # The pre-edit draft is preserved so Down can restore it.
    assert mock_ui._queued_edit_draft == "current draft"


def test_up_arrow_skips_exec_jobs(mock_ui):
    _exec = _queued_entry("ls", kind="exec")
    message = _queued_entry("hello")
    mock_ui._message_queue.put_nowait(_exec)
    mock_ui._message_queue.put_nowait(message)
    event = create_mock_event("draft")

    assert mock_ui._handle_up_arrow(event) is True
    assert mock_ui.queued_edit_entry is message
    assert event.current_buffer.text == "hello"


def test_up_arrow_falls_through_without_queued_messages(mock_ui):
    event = create_mock_event("draft")
    assert mock_ui._handle_up_arrow(event) is False
    assert mock_ui.queued_edit_entry is None


def test_up_arrow_recalls_older_queued_message(mock_ui):
    older = _queued_entry("older")
    newer = _queued_entry("newer")
    mock_ui._message_queue.put_nowait(older)
    mock_ui._message_queue.put_nowait(newer)
    event = create_mock_event()

    mock_ui._handle_up_arrow(event)
    assert mock_ui.queued_edit_entry is newer
    assert event.current_buffer.text == "newer"

    # The input field holds the recalled text untouched — Up keeps navigating.
    _set_input_buffer(mock_ui, "newer", len("newer"))
    mock_ui._handle_up_arrow(event)
    assert mock_ui.queued_edit_entry is older
    assert event.current_buffer.text == "older"


def test_up_arrow_at_oldest_queued_message_stays(mock_ui):
    entry = _queued_entry("only message")
    mock_ui._message_queue.put_nowait(entry)
    mock_ui._queued_edit_entry = entry
    # The input field holds the recalled text with the cursor at its end.
    _set_input_buffer(mock_ui, "only message", len("only message"))
    event = create_mock_event("only message")

    assert mock_ui._handle_up_arrow(event) is True
    assert mock_ui.queued_edit_entry is entry
    assert event.current_buffer.text == "only message"


def test_down_arrow_restores_draft(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui._message_queue.put_nowait(entry)
    event = create_mock_event("draft before recall")

    mock_ui._handle_up_arrow(event)
    assert event.current_buffer.text == "queued message"
    _set_input_buffer(mock_ui, "queued message", len("queued message"))

    assert mock_ui._handle_down_arrow(event) is True
    assert mock_ui.queued_edit_entry is None
    assert event.current_buffer.text == "draft before recall"
    assert event.current_buffer.cursor_position == len("draft before recall")


def test_down_arrow_moves_to_newer_queued_message(mock_ui):
    older = _queued_entry("older")
    newer = _queued_entry("newer")
    mock_ui._message_queue.put_nowait(older)
    mock_ui._message_queue.put_nowait(newer)
    mock_ui._queued_edit_entry = older
    _set_input_buffer(mock_ui, "older", len("older"))
    event = create_mock_event("older")

    assert mock_ui._handle_down_arrow(event) is True
    assert mock_ui.queued_edit_entry is newer
    assert event.current_buffer.text == "newer"


def test_up_arrow_drops_stale_edit_mode(mock_ui):
    # The recalled message's turn started while the user was editing it; the
    # next Up drops the stale edit mode instead of navigating from a ghost.
    entry = _queued_entry("queued message")
    mock_ui._message_queue.put_nowait(entry)
    event = create_mock_event("draft")

    mock_ui._handle_up_arrow(event)
    _set_input_buffer(mock_ui, "queued message", len("queued message"))
    mock_ui._message_queue.remove(entry)

    assert mock_ui._handle_up_arrow(event) is False
    assert mock_ui.queued_edit_entry is None
    # The pre-recall draft survives the stale drop.
    assert mock_ui._queued_edit_draft == "draft"


def test_up_arrow_after_stale_edit_recalls_without_clobbering_draft(mock_ui):
    # The recalled message's turn started; a still-waiting message is queued
    # behind it, so this Up recalls that one — but the original draft stays
    # saved.
    stale = _queued_entry("stale message")
    recalled = _queued_entry("recalled message")
    mock_ui._message_queue.put_nowait(stale)
    mock_ui._message_queue.put_nowait(recalled)
    event = create_mock_event("draft")

    mock_ui._handle_up_arrow(event)
    assert mock_ui.queued_edit_entry is recalled
    _set_input_buffer(mock_ui, "recalled message", len("recalled message"))
    mock_ui._message_queue.remove(recalled)  # the recalled turn started

    assert mock_ui._handle_up_arrow(event) is True
    assert mock_ui.queued_edit_entry is stale
    assert event.current_buffer.text == "stale message"
    assert mock_ui._queued_edit_draft == "draft"


def test_down_arrow_drops_stale_edit_mode(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui._message_queue.put_nowait(entry)
    mock_ui._queued_edit_entry = entry
    _set_input_buffer(mock_ui, "queued message", len("queued message"))
    event = create_mock_event("queued message")

    mock_ui._message_queue.remove(entry)

    assert mock_ui._handle_down_arrow(event) is False
    assert mock_ui.queued_edit_entry is None


def test_down_arrow_falls_through_when_not_editing(mock_ui):
    event = create_mock_event()
    assert mock_ui._handle_down_arrow(event) is False


def test_up_arrow_after_typing_falls_through_and_preserves_edit(mock_ui):
    # Once the user types into a recalled message, Up must fall through (history
    # recall) instead of navigating the queue over the in-progress edit — the
    # saved draft is the pre-recall text, so the edit is otherwise unrecoverable.
    entry = _queued_entry("queued message")
    mock_ui._message_queue.put_nowait(entry)
    event = create_mock_event("draft")

    mock_ui._handle_up_arrow(event)
    event.current_buffer.text = "queued message EDITED"
    event.current_buffer.cursor_position = len("queued message EDITED")
    _set_input_buffer(mock_ui, "queued message EDITED", len("queued message EDITED"))

    assert mock_ui._handle_up_arrow(event) is False
    assert event.current_buffer.text == "queued message EDITED"
    assert mock_ui.queued_edit_entry is entry  # Enter can still apply the edit


def test_down_arrow_after_typing_falls_through_and_preserves_edit(mock_ui):
    # Down after typing must not exit edit mode and restore the pre-recall
    # draft over the user's edit.
    entry = _queued_entry("queued message")
    mock_ui._message_queue.put_nowait(entry)
    event = create_mock_event("draft")

    mock_ui._handle_up_arrow(event)
    event.current_buffer.text = "queued message EDITED"
    event.current_buffer.cursor_position = len("queued message EDITED")
    _set_input_buffer(mock_ui, "queued message EDITED", len("queued message EDITED"))

    assert mock_ui._handle_down_arrow(event) is False
    assert event.current_buffer.text == "queued message EDITED"
    assert mock_ui.queued_edit_entry is entry


# ── Sub-agent picker trigger (UIMessageEditing + UIAgentPicker) ──────────


def test_down_arrow_opens_agent_picker_with_empty_buffer_and_live_sessions(mock_ui):
    event = create_mock_event()
    mock_ui.open_agent_picker = MagicMock(return_value=True)

    assert mock_ui._handle_down_arrow(event) is True

    mock_ui.open_agent_picker.assert_called_once()


def test_down_arrow_does_not_open_agent_picker_with_text_in_buffer(mock_ui):
    event = create_mock_event("some text")
    mock_ui.open_agent_picker = MagicMock(return_value=True)

    assert mock_ui._handle_down_arrow(event) is False

    mock_ui.open_agent_picker.assert_not_called()


def test_down_arrow_does_not_open_agent_picker_without_live_sessions(mock_ui):
    event = create_mock_event()
    mock_ui.open_agent_picker = MagicMock(return_value=False)

    assert mock_ui._handle_down_arrow(event) is False

    mock_ui.open_agent_picker.assert_called_once()


def test_up_arrow_after_cursor_move_falls_through(mock_ui):
    # Moving the cursor (even without typing) ends recall navigation too.
    entry = _queued_entry("queued message")
    mock_ui._message_queue.put_nowait(entry)
    event = create_mock_event("queued message")
    mock_ui._handle_up_arrow(event)
    event.current_buffer.cursor_position = 3
    _set_input_buffer(mock_ui, "queued message", 3)

    assert mock_ui._handle_up_arrow(event) is False
    assert event.current_buffer.text == "queued message"
    assert mock_ui.queued_edit_entry is entry


def test_enter_edits_queued_message_after_typing(mock_ui, setup_bindings):
    # Typing in a recalled message keeps it the Enter target: Enter still
    # applies the edit in place rather than submitting a new message.
    entry = _queued_entry("queued message")
    mock_ui._message_queue.put_nowait(entry)
    event = create_mock_event("draft")
    mock_ui._handle_up_arrow(event)
    event.current_buffer.text = "queued message EDITED"
    event.current_buffer.cursor_position = len("queued message EDITED")

    trigger_binding(setup_bindings, "c-m", event)

    mock_ui.edit_queued_message.assert_called_once_with(entry, "queued message EDITED")
    event.current_buffer.reset.assert_called_once()
    mock_ui._submit_user_message.assert_not_called()


def _set_input_buffer(mock_ui, text, cursor_position):
    mock_ui._input_field.buffer = MagicMock(text=text, cursor_position=cursor_position)


def test_recall_navigation_active_for_unmodified_recall(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui._queued_edit_entry = entry
    _set_input_buffer(mock_ui, "queued message", len("queued message"))
    assert mock_ui._recall_navigation_active() is True


def test_recall_navigation_inactive_without_entry(mock_ui):
    mock_ui._queued_edit_entry = None
    _set_input_buffer(mock_ui, "queued message", len("queued message"))
    assert mock_ui._recall_navigation_active() is False


def test_recall_navigation_inactive_after_typing(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui._queued_edit_entry = entry
    _set_input_buffer(mock_ui, "queued message edited", len("queued message edited"))
    assert mock_ui._recall_navigation_active() is False


def test_recall_navigation_inactive_after_cursor_moves(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui._queued_edit_entry = entry
    _set_input_buffer(mock_ui, "queued message", 3)
    assert mock_ui._recall_navigation_active() is False


def test_enter_edits_queued_message(mock_ui, setup_bindings):
    entry = _queued_entry("queued message")
    mock_ui._message_queue.put_nowait(entry)
    mock_ui._queued_edit_entry = entry
    mock_ui._queued_edit_draft = ""
    event = create_mock_event("edited text")

    trigger_binding(setup_bindings, "c-m", event)

    mock_ui.edit_queued_message.assert_called_once_with(entry, "edited text")
    event.current_buffer.reset.assert_called_once()
    mock_ui._submit_user_message.assert_not_called()
    assert mock_ui.queued_edit_entry is None


def test_enter_empty_edit_cancels_and_restores_draft(mock_ui, setup_bindings):
    entry = _queued_entry("queued message")
    mock_ui._message_queue.put_nowait(entry)
    mock_ui._queued_edit_entry = entry
    mock_ui._queued_edit_draft = "saved draft"
    event = create_mock_event("   ")

    trigger_binding(setup_bindings, "c-m", event)

    assert event.current_buffer.text == "saved draft"
    mock_ui.edit_queued_message.assert_not_called()
    mock_ui._submit_user_message.assert_not_called()


def test_enter_after_turn_started_submits_normally(mock_ui, setup_bindings):
    # The recalled message's turn started before Enter; the edit is refused and
    # the text falls through to the normal submit path as a new message.
    entry = _queued_entry("queued message")
    mock_ui.edit_queued_message.return_value = False
    mock_ui._queued_edit_entry = entry
    event = create_mock_event("edited text")

    trigger_binding(setup_bindings, "c-m", event)

    mock_ui._submit_user_message.assert_called_once()
    assert mock_ui.queued_edit_entry is None


def test_enter_submit_message(mock_ui, setup_bindings):
    event = create_mock_event("hello world")
    mock_ui.classify_input.return_value = "message"
    trigger_binding(setup_bindings, "c-m", event)
    event.current_buffer.append_to_history.assert_called_once()
    mock_ui._submit_user_message.assert_called_once()
    event.current_buffer.reset.assert_called_once()


@pytest.mark.asyncio
async def test_ctrl_v_image_found(mock_ui, setup_bindings):
    event = create_mock_event()

    with patch(
        "zrb.llm.util.clipboard.get_clipboard_image", new_callable=AsyncMock
    ) as mock_get_img:
        mock_get_img.return_value = b"fake_image_data"
        trigger_binding(setup_bindings, "c-v", event)

        # Wait for background task
        assert len(mock_ui._background_tasks) == 1
        await list(mock_ui._background_tasks)[0]

        assert len(mock_ui._pending_attachments) == 1
        assert mock_ui._pending_attachments[0].media_type == "image/png"
        mock_ui.invalidate_ui.assert_called_once()


@pytest.mark.asyncio
async def test_ctrl_v_no_image_has_hint(mock_ui, setup_bindings):
    event = create_mock_event()

    with patch(
        "zrb.llm.util.clipboard.get_clipboard_image", new_callable=AsyncMock
    ) as mock_get_img:
        with patch("zrb.llm.util.clipboard.missing_tool_hint") as mock_hint:
            mock_get_img.return_value = None
            mock_hint.return_value = "Missing tool hint"

            trigger_binding(setup_bindings, "c-v", event)

            # Wait for background task
            assert len(mock_ui._background_tasks) == 1
            await list(mock_ui._background_tasks)[0]

            assert len(mock_ui._pending_attachments) == 0
            mock_ui.invalidate_ui.assert_called_once()
            assert any("Missing tool hint" in out for out in mock_ui.outputs)


@pytest.mark.asyncio
async def test_ctrl_v_no_image_no_hint(mock_ui, setup_bindings):
    event = create_mock_event()

    with patch(
        "zrb.llm.util.clipboard.get_clipboard_image", new_callable=AsyncMock
    ) as mock_get_img:
        with patch("zrb.llm.util.clipboard.missing_tool_hint") as mock_hint:
            with patch("prompt_toolkit.application.get_app") as mock_get_app:
                mock_get_img.return_value = None
                mock_hint.return_value = None

                app_mock = MagicMock()
                mock_get_app.return_value = app_mock

                trigger_binding(setup_bindings, "c-v", event)

                # Wait for background task
                assert len(mock_ui._background_tasks) == 1
                await list(mock_ui._background_tasks)[0]

                app_mock.layout.focus.assert_called_with(mock_ui._input_field)
                mock_ui._input_field.buffer.paste_clipboard_data.assert_called_with(
                    "pasted_text"
                )


# --- Integration: real keybinding + real classification/dispatch/handlers ---
#
# These drive the actual Enter binding through BaseUICommands's real
# classify_input -> schedule_command -> dispatch_command -> _run_command_chain
# -> _handle_* path. Only leaf IO (LLM submit, hook manager, the btw side-query)
# is stubbed, so the routing regressions — especially a non-"/" ">" redirect
# token — are caught end-to-end rather than behind mocked routing.

from zrb.llm.ui.base.commands import BaseUICommands  # noqa: E402


class IntegrationUI:
    """`BaseUICommands`, `UIKeybindings` and `UIMessageEditing` are all
    composed (not inherited): their handlers read state through the UI
    reference, so `self._cmds`/`self._keybindings`/`self._message_editing`
    plus the `__getattr__` fallback below keep `self.classify_input(...)` /
    `self.schedule_command(...)` working exactly as before."""

    def __init__(self):
        self._exit_commands = ["/exit"]
        self._info_commands = ["/help"]
        self._save_commands = ["/save"]
        self._load_commands = ["/load"]
        self._rewind_commands = ["/rewind"]
        self._redirect_output_commands = [">"]  # non-"/" token (the regression)
        self._attach_commands = ["/attach"]
        self._photo_commands = []
        self._yolo_toggle_commands = ["/yolo"]
        self._set_model_commands = ["/model"]
        self._exec_commands = ["/exec"]
        self._btw_commands = ["/btw"]
        self._plan_commands = ["/plan"]
        self._summarize_commands = ["/summarize"]
        self._copy_commands = []
        self._voice_commands = []
        self._voice_mode_active = False
        self._voice_recording_active = False
        self._voice_task = None
        self._voice_stop_event = None
        self._custom_commands = []
        self._is_thinking = False
        self._background_tasks = set()
        self._conversation_session_name = "default"
        self._snapshot_manager = None
        self._llm_task = MagicMock()
        self.last_output = "AI RESPONSE TEXT"
        self._input_field = MagicMock()
        self._output_field = MagicMock()
        self.submitted = []
        self.outputs = []
        self.btw_questions = []
        self.execute_hook = MagicMock()
        self.execute_hook_blocking = AsyncMock(return_value=[])
        # Leaf collaborators only.
        self._handle_confirmation = MagicMock(return_value=False)

        self._cmds = BaseUICommands(self)
        self._keybindings = UIKeybindings(self)
        self._message_editing = UIMessageEditing(self)

    def __getattr__(self, name):
        cmds = self.__dict__.get("_cmds")
        if cmds is not None:
            for collaborator_attr in ("", "_conversation", "_models", "_exec"):
                holder = getattr(cmds, collaborator_attr) if collaborator_attr else cmds
                if hasattr(holder, name):
                    return getattr(holder, name)
        for part_attr in ("_keybindings", "_message_editing"):
            part = self.__dict__.get(part_attr)
            if part is not None and hasattr(part, name):
                return getattr(part, name)
        raise AttributeError(name)

    def setup_app_keybindings(self, app_keybindings, llm_task):
        return self._keybindings.setup_app_keybindings(app_keybindings, llm_task)

    @property
    def _queued_edit_entry(self):
        return self._message_editing._queued_edit_entry

    @_queued_edit_entry.setter
    def _queued_edit_entry(self, value):
        self._message_editing._queued_edit_entry = value

    @property
    def _queued_edit_draft(self):
        return self._message_editing._queued_edit_draft

    @_queued_edit_draft.setter
    def _queued_edit_draft(self, value):
        self._message_editing._queued_edit_draft = value

    def append_to_output(self, text, end="\n"):
        self.outputs.append(str(text))

    def _submit_user_message(self, task, text):
        self.submitted.append(text)

    async def _stream_btw_response(self, task, question):
        self.btw_questions.append(question)


@pytest.fixture
def integration_ui():
    ui = IntegrationUI()
    kb = KeyBindings()
    ui.setup_app_keybindings(kb, ui._llm_task)
    return ui, kb


async def _drain(ui):
    """Await every scheduled task, including ones spawned during dispatch."""
    while ui._background_tasks:
        task = next(iter(ui._background_tasks))
        try:
            await task
        except Exception:
            pass
        ui._background_tasks.discard(task)


@pytest.mark.asyncio
async def test_integration_redirect_token_writes_file(integration_ui, tmp_path):
    # The bug that started this: ">" is a configured (non-"/") command token.
    # Driving the real keybinding must run the redirect handler, not the LLM.
    ui, kb = integration_ui
    out = tmp_path / "sub" / "out.txt"
    event = create_mock_event(f"> {out}")

    trigger_binding(kb, "c-m", event)
    assert len(ui._background_tasks) == 1
    await _drain(ui)

    assert out.read_text() == "AI RESPONSE TEXT"  # redirect actually ran
    assert ui.submitted == []  # NOT forwarded to the LLM
    assert ui.execute_hook_blocking.call_args.args[0] == HookEvent.PRE_COMMAND
    assert ui.execute_hook.call_args.args[0] == HookEvent.POST_COMMAND


def test_integration_plain_message_goes_to_llm(integration_ui):
    ui, kb = integration_ui
    event = create_mock_event("explain this code")

    trigger_binding(kb, "c-m", event)

    assert ui.submitted == ["explain this code"]
    assert not ui._background_tasks  # no command dispatched, no hooks


def test_integration_redirect_gated_while_thinking(integration_ui, tmp_path):
    ui, kb = integration_ui
    ui._is_thinking = True
    out = tmp_path / "out.txt"
    event = create_mock_event(f"> {out}")

    trigger_binding(kb, "c-m", event)

    assert not ui._background_tasks  # command held while thinking
    assert ui.submitted == []
    assert not out.exists()


@pytest.mark.asyncio
async def test_integration_slash_command_runs(integration_ui):
    ui, kb = integration_ui
    event = create_mock_event("/help")

    trigger_binding(kb, "c-m", event)
    await _drain(ui)

    assert any("Keyboard Shortcuts" in o for o in ui.outputs)  # help printed
    assert ui.submitted == []
    assert ui.execute_hook.call_args.args[0] == HookEvent.POST_COMMAND


@pytest.mark.asyncio
async def test_integration_btw_runs_while_thinking(integration_ui):
    # /btw is a run-while-thinking command: it dispatches and runs even while
    # the LLM is responding.
    ui, kb = integration_ui
    ui._is_thinking = True
    event = create_mock_event("/btw are you there")

    trigger_binding(kb, "c-m", event)
    assert len(ui._background_tasks) >= 1
    await _drain(ui)

    assert ui.btw_questions == ["are you there"]
    assert ui.submitted == []


# ── Voice push-to-talk keybinding (ADR-0076) ──────────────────────────


def test_ctrl_c_cancels_in_flight_voice_task(mock_ui, setup_bindings):
    """Ctrl+C with an empty buffer cancels any in-flight voice task."""
    voice_task = MagicMock()
    voice_task.done.return_value = False
    mock_ui._voice_task = voice_task
    event = create_mock_event("")

    trigger_binding(setup_bindings, "c-c", event)

    voice_task.cancel.assert_called_once()


def test_voice_ptt_not_focused_inserts_space(mock_ui, setup_bindings):
    """When the input field isn't focused, the PTT key inserts a literal space."""
    mock_ui._voice_mode_active = True
    event = create_mock_event()
    event.app.layout.has_focus.return_value = False

    trigger_binding(setup_bindings, " ", event)

    mock_ui._input_field.buffer.insert_text.assert_called_once_with(" ")


def test_voice_ptt_stop_then_debounced_second_press(mock_ui, setup_bindings):
    """First press while recording stops + exits; a too-fast 2nd press is ignored."""
    mock_ui._voice_mode_active = True
    mock_ui._voice_recording_active = True
    mock_ui._voice_stop_event = asyncio.Event()
    event = create_mock_event()
    event.app.layout.has_focus.return_value = True

    with patch("time.time", side_effect=[100.0, 100.05]):
        trigger_binding(setup_bindings, " ", event)  # stop branch
        assert mock_ui._voice_recording_active is False
        assert mock_ui._voice_mode_active is False
        assert mock_ui._voice_stop_event.is_set()
        outputs_after_stop = len(mock_ui.outputs)
        trigger_binding(setup_bindings, " ", event)  # debounced no-op
        assert len(mock_ui.outputs) == outputs_after_stop

    assert any("Stopped" in o for o in mock_ui.outputs)


@pytest.mark.asyncio
async def test_voice_ptt_start_records_and_inserts(mock_ui, setup_bindings):
    """A press starts recording; transcribed text is inserted on completion."""
    mock_ui._voice_mode_active = True
    fake_engine = MagicMock()
    fake_engine._transcriber = None
    fake_engine.start_listening = AsyncMock(return_value="hello world")
    event = create_mock_event()
    event.app.layout.has_focus.return_value = True

    with (
        patch("zrb.llm.voice.VoiceEngine", return_value=fake_engine),
        patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "openai"}),
    ):
        trigger_binding(setup_bindings, " ", event)
        assert mock_ui._voice_recording_active is True
        await _drain(mock_ui)

    fake_engine.start_listening.assert_awaited_once()
    mock_ui._input_field.buffer.insert_text.assert_called_with("hello world")
    assert any("Transcribed (2 words)" in o for o in mock_ui.outputs)
    assert mock_ui._voice_recording_active is False


@pytest.mark.asyncio
async def test_voice_ptt_no_speech_detected(mock_ui, setup_bindings):
    """An empty transcription reports 'No speech detected'."""
    mock_ui._voice_mode_active = True
    fake_engine = MagicMock()
    fake_engine._transcriber = None
    fake_engine.start_listening = AsyncMock(return_value="")
    event = create_mock_event()

    with (
        patch("zrb.llm.voice.VoiceEngine", return_value=fake_engine),
        patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "openai"}),
    ):
        trigger_binding(setup_bindings, " ", event)
        await _drain(mock_ui)

    assert any("No speech detected" in o for o in mock_ui.outputs)


@pytest.mark.asyncio
async def test_voice_ptt_start_listening_error(mock_ui, setup_bindings):
    """A recording error surfaces and resets voice state."""
    mock_ui._voice_mode_active = True
    fake_engine = MagicMock()
    fake_engine._transcriber = None
    fake_engine.start_listening = AsyncMock(side_effect=RuntimeError("mic fail"))
    event = create_mock_event()

    with (
        patch("zrb.llm.voice.VoiceEngine", return_value=fake_engine),
        patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "openai"}),
    ):
        trigger_binding(setup_bindings, " ", event)
        await _drain(mock_ui)

    assert any("Voice error" in o and "mic fail" in o for o in mock_ui.outputs)
    assert mock_ui._voice_mode_active is False


@pytest.mark.asyncio
async def test_voice_ptt_vosk_downloads_model_first(mock_ui, setup_bindings):
    """The vosk backend downloads the model on first use before recording."""
    mock_ui._voice_mode_active = True
    fake_engine = MagicMock()
    fake_engine.is_ready = False
    fake_engine.is_vosk_model_ready = MagicMock(return_value=False)
    fake_engine.download_vosk_model = AsyncMock()
    fake_engine.start_listening = AsyncMock(return_value="hi")
    event = create_mock_event()

    with (
        patch("zrb.llm.voice.VoiceEngine", return_value=fake_engine),
        patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "vosk"}),
    ):
        trigger_binding(setup_bindings, " ", event)
        await _drain(mock_ui)

    fake_engine.download_vosk_model.assert_awaited_once()
    assert any("Downloading voice model" in o for o in mock_ui.outputs)
    assert any("Voice model ready" in o for o in mock_ui.outputs)


@pytest.mark.asyncio
async def test_voice_ptt_vosk_download_error_aborts(mock_ui, setup_bindings):
    """A model-download failure surfaces and skips recording."""
    mock_ui._voice_mode_active = True
    fake_engine = MagicMock()
    fake_engine.is_ready = False
    fake_engine.is_vosk_model_ready = MagicMock(return_value=False)
    fake_engine.download_vosk_model = AsyncMock(side_effect=RuntimeError("net down"))
    fake_engine.start_listening = AsyncMock(return_value="hi")
    event = create_mock_event()

    with (
        patch("zrb.llm.voice.VoiceEngine", return_value=fake_engine),
        patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "vosk"}),
    ):
        trigger_binding(setup_bindings, " ", event)
        await _drain(mock_ui)

    assert any("Voice error" in o and "net down" in o for o in mock_ui.outputs)
    fake_engine.start_listening.assert_not_awaited()
