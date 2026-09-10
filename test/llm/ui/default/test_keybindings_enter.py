from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.clipboard import ClipboardData
from prompt_toolkit.key_binding import KeyBindings

from zrb.llm.ui.base.message_queue import MessageQueue, QueuedMessage
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


def _queued_entry(text, kind="message"):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind=kind, run=run)


def _set_input_buffer(mock_ui, text, cursor_position):
    mock_ui.input_field.buffer = MagicMock(text=text, cursor_position=cursor_position)


def test_enter_command_routes_to_dispatch(mock_ui, setup_bindings):
    # A recognized command (any token, e.g. ">" redirect) goes through the
    # hook-wrapped async dispatch — never submitted to the LLM directly.
    # Guards the regression where ">" redirect was swallowed.
    event = create_mock_event("> ~/coba.txt")
    mock_ui.classify_input.return_value = "command"
    trigger_binding(setup_bindings, "c-m", event)
    mock_ui.schedule_command.assert_called_once_with("> ~/coba.txt")
    event.current_buffer.reset.assert_called_once()
    assert not mock_ui.submit_user_message.called


def test_enter_command_gated_while_thinking(mock_ui, setup_bindings):
    # A non-thinking command typed while the LLM is responding is held (not
    # dispatched, not submitted, buffer kept) — matches main.
    event = create_mock_event("/save x")
    mock_ui.classify_input.return_value = "command"
    mock_ui.is_thinking = True
    trigger_binding(setup_bindings, "c-m", event)
    assert not mock_ui.schedule_command.called
    assert not mock_ui.submit_user_message.called
    assert not event.current_buffer.reset.called


def test_enter_message_while_thinking_is_queued(mock_ui, setup_bindings):
    # Typing while the assistant works queues the message (the message loop runs
    # one job at a time) instead of swallowing the Enter.
    event = create_mock_event("hello")
    mock_ui.classify_input.return_value = "message"
    mock_ui.is_thinking = True
    trigger_binding(setup_bindings, "c-m", event)
    mock_ui.submit_user_message.assert_called_once()
    event.current_buffer.reset.assert_called_once()
    assert not mock_ui.schedule_command.called


@pytest.mark.asyncio
async def test_enter_while_viewing_sends_message_to_sub_agent(mock_ui, setup_bindings):
    event = create_mock_event("hello sub-agent")
    mock_ui.viewing_agent_id = "abc123"
    fake = _FakeLiveRegistry()

    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry", fake
    ):
        trigger_binding(setup_bindings, "c-m", event)
        for task in list(mock_ui.background_tasks):
            await task
        assert fake.sent == [("test_session", "abc123", "hello sub-agent")]
        event.current_buffer.reset.assert_called_once()
        # The message is echoed into the sub-agent's own buffer so its live
        # view reads as a conversation.
        fake.entry.buffered_ui.append_to_output.assert_called_once_with(
            "\n💬 hello sub-agent\n"
        )
        assert not mock_ui.submit_user_message.called
        assert not mock_ui.schedule_command.called
        assert not mock_ui.classify_input.called


@pytest.mark.asyncio
async def test_enter_while_viewing_sends_slash_command_as_message(
    mock_ui, setup_bindings
):
    # While viewing, even a "/..." line goes to the sub-agent as a plain
    # message — it must never dispatch as a main-session command.
    event = create_mock_event("/save x")
    mock_ui.viewing_agent_id = "abc123"
    fake = _FakeLiveRegistry()

    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry", fake
    ):
        trigger_binding(setup_bindings, "c-m", event)
        for task in list(mock_ui.background_tasks):
            await task
        assert fake.sent == [("test_session", "abc123", "/save x")]

    assert not mock_ui.schedule_command.called
    assert not mock_ui.submit_user_message.called


def test_up_arrow_recalls_queued_message(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    event = create_mock_event("current draft")

    assert mock_ui.handle_up_arrow(event) is True
    assert event.current_buffer.text == "queued message"
    assert event.current_buffer.cursor_position == len("queued message")
    assert mock_ui.queued_edit_entry is entry
    # The pre-edit draft is preserved so Down can restore it.
    assert mock_ui.queued_edit_draft == "current draft"


def test_up_arrow_skips_exec_jobs(mock_ui):
    _exec = _queued_entry("ls", kind="exec")
    message = _queued_entry("hello")
    mock_ui.effective_message_queue.put_nowait(_exec)
    mock_ui.effective_message_queue.put_nowait(message)
    event = create_mock_event("draft")

    assert mock_ui.handle_up_arrow(event) is True
    assert mock_ui.queued_edit_entry is message
    assert event.current_buffer.text == "hello"


def test_up_arrow_falls_through_without_queued_messages(mock_ui):
    event = create_mock_event("draft")
    assert mock_ui.handle_up_arrow(event) is False
    assert mock_ui.queued_edit_entry is None


def test_up_arrow_recalls_older_queued_message(mock_ui):
    older = _queued_entry("older")
    newer = _queued_entry("newer")
    mock_ui.effective_message_queue.put_nowait(older)
    mock_ui.effective_message_queue.put_nowait(newer)
    event = create_mock_event()

    mock_ui.handle_up_arrow(event)
    assert mock_ui.queued_edit_entry is newer
    assert event.current_buffer.text == "newer"

    # The input field holds the recalled text untouched — Up keeps navigating.
    _set_input_buffer(mock_ui, "newer", len("newer"))
    mock_ui.handle_up_arrow(event)
    assert mock_ui.queued_edit_entry is older
    assert event.current_buffer.text == "older"


def test_up_arrow_at_oldest_queued_message_stays(mock_ui):
    entry = _queued_entry("only message")
    mock_ui.effective_message_queue.put_nowait(entry)
    mock_ui.queued_edit_entry = entry
    # The input field holds the recalled text with the cursor at its end.
    _set_input_buffer(mock_ui, "only message", len("only message"))
    event = create_mock_event("only message")

    assert mock_ui.handle_up_arrow(event) is True
    assert mock_ui.queued_edit_entry is entry
    assert event.current_buffer.text == "only message"


def test_down_arrow_restores_draft(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    event = create_mock_event("draft before recall")

    mock_ui.handle_up_arrow(event)
    assert event.current_buffer.text == "queued message"
    _set_input_buffer(mock_ui, "queued message", len("queued message"))

    assert mock_ui.handle_down_arrow(event) is True
    assert mock_ui.queued_edit_entry is None
    assert event.current_buffer.text == "draft before recall"
    assert event.current_buffer.cursor_position == len("draft before recall")


def test_down_arrow_moves_to_newer_queued_message(mock_ui):
    older = _queued_entry("older")
    newer = _queued_entry("newer")
    mock_ui.effective_message_queue.put_nowait(older)
    mock_ui.effective_message_queue.put_nowait(newer)
    mock_ui.queued_edit_entry = older
    _set_input_buffer(mock_ui, "older", len("older"))
    event = create_mock_event("older")

    assert mock_ui.handle_down_arrow(event) is True
    assert mock_ui.queued_edit_entry is newer
    assert event.current_buffer.text == "newer"


def test_up_arrow_drops_stale_edit_mode(mock_ui):
    # The recalled message's turn started while the user was editing it; the
    # next Up drops the stale edit mode instead of navigating from a ghost.
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    event = create_mock_event("draft")

    mock_ui.handle_up_arrow(event)
    _set_input_buffer(mock_ui, "queued message", len("queued message"))
    mock_ui.effective_message_queue.remove(entry)

    assert mock_ui.handle_up_arrow(event) is False
    assert mock_ui.queued_edit_entry is None
    # The pre-recall draft survives the stale drop.
    assert mock_ui.queued_edit_draft == "draft"


def test_up_arrow_after_stale_edit_recalls_without_clobbering_draft(mock_ui):
    # The recalled message's turn started; a still-waiting message is queued
    # behind it, so this Up recalls that one — but the original draft stays
    # saved.
    stale = _queued_entry("stale message")
    recalled = _queued_entry("recalled message")
    mock_ui.effective_message_queue.put_nowait(stale)
    mock_ui.effective_message_queue.put_nowait(recalled)
    event = create_mock_event("draft")

    mock_ui.handle_up_arrow(event)
    assert mock_ui.queued_edit_entry is recalled
    _set_input_buffer(mock_ui, "recalled message", len("recalled message"))
    mock_ui.effective_message_queue.remove(recalled)  # the recalled turn started

    assert mock_ui.handle_up_arrow(event) is True
    assert mock_ui.queued_edit_entry is stale
    assert event.current_buffer.text == "stale message"
    assert mock_ui.queued_edit_draft == "draft"


def test_down_arrow_drops_stale_edit_mode(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    mock_ui.queued_edit_entry = entry
    _set_input_buffer(mock_ui, "queued message", len("queued message"))
    event = create_mock_event("queued message")

    mock_ui.effective_message_queue.remove(entry)

    assert mock_ui.handle_down_arrow(event) is False
    assert mock_ui.queued_edit_entry is None


def test_down_arrow_falls_through_when_not_editing(mock_ui):
    event = create_mock_event()
    assert mock_ui.handle_down_arrow(event) is False
