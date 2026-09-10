import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prompt_toolkit.clipboard import ClipboardData
from prompt_toolkit.key_binding import KeyBindings

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


async def _drain(ui):
    """Await every scheduled task, including ones spawned during dispatch."""
    while ui.background_tasks:
        task = next(iter(ui.background_tasks))
        try:
            await task
        except Exception:
            pass
        ui.background_tasks.discard(task)


def test_ctrl_c_cancels_in_flight_voice_task(mock_ui, setup_bindings):
    """Ctrl+C with an empty buffer cancels any in-flight voice task."""
    voice_task = MagicMock()
    voice_task.done.return_value = False
    mock_ui.voice_task = voice_task
    event = create_mock_event("")

    trigger_binding(setup_bindings, "c-c", event)

    voice_task.cancel.assert_called_once()


def test_voice_ptt_not_focused_inserts_space(mock_ui, setup_bindings):
    """When the input field isn't focused, the PTT key inserts a literal space."""
    mock_ui.voice_mode_active = True
    event = create_mock_event()
    event.app.layout.has_focus.return_value = False

    trigger_binding(setup_bindings, " ", event)

    mock_ui.input_field.buffer.insert_text.assert_called_once_with(" ")


def test_voice_ptt_stop_then_debounced_second_press(mock_ui, setup_bindings):
    """First press while recording stops + exits; a too-fast 2nd press is ignored."""
    mock_ui.voice_mode_active = True
    mock_ui.voice_recording_active = True
    mock_ui.voice_stop_event = asyncio.Event()
    event = create_mock_event()
    event.app.layout.has_focus.return_value = True

    with patch("time.time", side_effect=[100.0, 100.05]):
        trigger_binding(setup_bindings, " ", event)  # stop branch
        assert mock_ui.voice_recording_active is False
        assert mock_ui.voice_mode_active is False
        assert mock_ui.voice_stop_event.is_set()
        outputs_after_stop = len(mock_ui.outputs)
        trigger_binding(setup_bindings, " ", event)  # debounced no-op
        assert len(mock_ui.outputs) == outputs_after_stop

    assert any("Stopped" in o for o in mock_ui.outputs)


@pytest.mark.asyncio
async def test_voice_ptt_start_records_and_inserts(mock_ui, setup_bindings):
    """A press starts recording; transcribed text is inserted on completion."""
    mock_ui.voice_mode_active = True
    fake_engine = MagicMock()
    fake_engine.start_listening = AsyncMock(return_value="hello world")
    event = create_mock_event()
    event.app.layout.has_focus.return_value = True

    with (
        patch("zrb.llm.voice.VoiceEngine", return_value=fake_engine),
        patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "openai"}),
    ):
        trigger_binding(setup_bindings, " ", event)
        assert mock_ui.voice_recording_active is True
        await _drain(mock_ui)

    fake_engine.start_listening.assert_awaited_once()
    mock_ui.input_field.buffer.insert_text.assert_called_with("hello world")
    assert any("Transcribed (2 words)" in o for o in mock_ui.outputs)
    assert mock_ui.voice_recording_active is False


@pytest.mark.asyncio
async def test_voice_ptt_no_speech_detected(mock_ui, setup_bindings):
    """An empty transcription reports 'No speech detected'."""
    mock_ui.voice_mode_active = True
    fake_engine = MagicMock()
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
    mock_ui.voice_mode_active = True
    fake_engine = MagicMock()
    fake_engine.start_listening = AsyncMock(side_effect=RuntimeError("mic fail"))
    event = create_mock_event()

    with (
        patch("zrb.llm.voice.VoiceEngine", return_value=fake_engine),
        patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "openai"}),
    ):
        trigger_binding(setup_bindings, " ", event)
        await _drain(mock_ui)

    assert any("Voice error" in o and "mic fail" in o for o in mock_ui.outputs)
    assert mock_ui.voice_mode_active is False


@pytest.mark.asyncio
async def test_voice_ptt_vosk_downloads_model_first(mock_ui, setup_bindings):
    """The vosk backend downloads the model on first use before recording."""
    mock_ui.voice_mode_active = True
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
    mock_ui.voice_mode_active = True
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
