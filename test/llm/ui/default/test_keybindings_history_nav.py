from unittest.mock import AsyncMock, MagicMock, patch

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


def _queued_entry(text, kind="message"):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind=kind, run=run)


def _set_input_buffer(mock_ui, text, cursor_position):
    mock_ui.input_field.buffer = MagicMock(text=text, cursor_position=cursor_position)


def test_up_arrow_after_typing_falls_through_and_preserves_edit(mock_ui):
    # Once the user types into a recalled message, Up must fall through (history
    # recall) instead of navigating the queue over the in-progress edit — the
    # saved draft is the pre-recall text, so the edit is otherwise unrecoverable.
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    event = create_mock_event("draft")

    mock_ui.handle_up_arrow(event)
    event.current_buffer.text = "queued message EDITED"
    event.current_buffer.cursor_position = len("queued message EDITED")
    _set_input_buffer(mock_ui, "queued message EDITED", len("queued message EDITED"))

    assert mock_ui.handle_up_arrow(event) is False
    assert event.current_buffer.text == "queued message EDITED"
    assert mock_ui.queued_edit_entry is entry  # Enter can still apply the edit


def test_down_arrow_after_typing_falls_through_and_preserves_edit(mock_ui):
    # Down after typing must not exit edit mode and restore the pre-recall
    # draft over the user's edit.
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    event = create_mock_event("draft")

    mock_ui.handle_up_arrow(event)
    event.current_buffer.text = "queued message EDITED"
    event.current_buffer.cursor_position = len("queued message EDITED")
    _set_input_buffer(mock_ui, "queued message EDITED", len("queued message EDITED"))

    assert mock_ui.handle_down_arrow(event) is False
    assert event.current_buffer.text == "queued message EDITED"
    assert mock_ui.queued_edit_entry is entry


def test_down_arrow_opens_agent_picker_with_empty_buffer_and_live_sessions(mock_ui):
    event = create_mock_event()
    mock_ui.open_agent_picker = MagicMock(return_value=True)

    assert mock_ui.handle_down_arrow(event) is True

    mock_ui.open_agent_picker.assert_called_once()


def test_down_arrow_does_not_open_agent_picker_with_text_in_buffer(mock_ui):
    event = create_mock_event("some text")
    mock_ui.open_agent_picker = MagicMock(return_value=True)

    assert mock_ui.handle_down_arrow(event) is False

    mock_ui.open_agent_picker.assert_not_called()


def test_down_arrow_does_not_open_agent_picker_without_live_sessions(mock_ui):
    event = create_mock_event()
    mock_ui.open_agent_picker = MagicMock(return_value=False)

    assert mock_ui.handle_down_arrow(event) is False

    mock_ui.open_agent_picker.assert_called_once()


def test_up_arrow_after_cursor_move_falls_through(mock_ui):
    # Moving the cursor (even without typing) ends recall navigation too.
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    event = create_mock_event("queued message")
    mock_ui.handle_up_arrow(event)
    event.current_buffer.cursor_position = 3
    _set_input_buffer(mock_ui, "queued message", 3)

    assert mock_ui.handle_up_arrow(event) is False
    assert event.current_buffer.text == "queued message"
    assert mock_ui.queued_edit_entry is entry


def test_enter_edits_queued_message_after_typing(mock_ui, setup_bindings):
    # Typing in a recalled message keeps it the Enter target: Enter still
    # applies the edit in place rather than submitting a new message.
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    event = create_mock_event("draft")
    mock_ui.handle_up_arrow(event)
    event.current_buffer.text = "queued message EDITED"
    event.current_buffer.cursor_position = len("queued message EDITED")

    trigger_binding(setup_bindings, "c-m", event)

    mock_ui.edit_queued_message.assert_called_once_with(entry, "queued message EDITED")
    event.current_buffer.reset.assert_called_once()
    mock_ui.submit_user_message.assert_not_called()


def test_recall_navigation_active_for_unmodified_recall(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui.queued_edit_entry = entry
    _set_input_buffer(mock_ui, "queued message", len("queued message"))
    assert mock_ui.recall_navigation_active() is True


def test_recall_navigation_inactive_without_entry(mock_ui):
    mock_ui.queued_edit_entry = None
    _set_input_buffer(mock_ui, "queued message", len("queued message"))
    assert mock_ui.recall_navigation_active() is False


def test_recall_navigation_inactive_after_typing(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui.queued_edit_entry = entry
    _set_input_buffer(mock_ui, "queued message edited", len("queued message edited"))
    assert mock_ui.recall_navigation_active() is False


def test_recall_navigation_inactive_after_cursor_moves(mock_ui):
    entry = _queued_entry("queued message")
    mock_ui.queued_edit_entry = entry
    _set_input_buffer(mock_ui, "queued message", 3)
    assert mock_ui.recall_navigation_active() is False


def test_enter_edits_queued_message(mock_ui, setup_bindings):
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    mock_ui.queued_edit_entry = entry
    mock_ui.queued_edit_draft = ""
    event = create_mock_event("edited text")

    trigger_binding(setup_bindings, "c-m", event)

    mock_ui.edit_queued_message.assert_called_once_with(entry, "edited text")
    event.current_buffer.reset.assert_called_once()
    mock_ui.submit_user_message.assert_not_called()
    assert mock_ui.queued_edit_entry is None


def test_enter_empty_edit_cancels_and_restores_draft(mock_ui, setup_bindings):
    entry = _queued_entry("queued message")
    mock_ui.effective_message_queue.put_nowait(entry)
    mock_ui.queued_edit_entry = entry
    mock_ui.queued_edit_draft = "saved draft"
    event = create_mock_event("   ")

    trigger_binding(setup_bindings, "c-m", event)

    assert event.current_buffer.text == "saved draft"
    mock_ui.edit_queued_message.assert_not_called()
    mock_ui.submit_user_message.assert_not_called()


def test_enter_after_turn_started_submits_normally(mock_ui, setup_bindings):
    # The recalled message's turn started before Enter; the edit is refused and
    # the text falls through to the normal submit path as a new message.
    entry = _queued_entry("queued message")
    mock_ui.edit_queued_message.return_value = False
    mock_ui.queued_edit_entry = entry
    event = create_mock_event("edited text")

    trigger_binding(setup_bindings, "c-m", event)

    mock_ui.submit_user_message.assert_called_once()
    assert mock_ui.queued_edit_entry is None


def test_enter_submit_message(mock_ui, setup_bindings):
    event = create_mock_event("hello world")
    mock_ui.classify_input.return_value = "message"
    trigger_binding(setup_bindings, "c-m", event)
    event.current_buffer.append_to_history.assert_called_once()
    mock_ui.submit_user_message.assert_called_once()
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
        assert len(mock_ui.background_tasks) == 1
        await list(mock_ui.background_tasks)[0]

        assert len(mock_ui.pending_attachments) == 1
        assert mock_ui.pending_attachments[0].media_type == "image/png"
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
            assert len(mock_ui.background_tasks) == 1
            await list(mock_ui.background_tasks)[0]

            assert len(mock_ui.pending_attachments) == 0
            mock_ui.invalidate_ui.assert_called_once()
            assert any("Missing tool hint" in out for out in mock_ui.outputs)
