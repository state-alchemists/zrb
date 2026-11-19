"""Doubles shared by the keybinding tests: the stand-in default `UI` that
composes the real keybinding, message-editing and picker parts, and the two
helpers that build a `prompt_toolkit` event and fire a binding at it."""

from unittest.mock import MagicMock

from prompt_toolkit.clipboard import ClipboardData

from zrb.llm.presentation.ui.base.message_queue import MessageQueue
from zrb.llm.presentation.ui.default.agent_picker import UIAgentPicker
from zrb.llm.presentation.ui.default.keybindings import UIKeybindings
from zrb.llm.presentation.ui.default.message_editing import UIMessageEditing


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
        # This double is its own display: the parts reach the output surface
        # through it, exactly as the real default `UI` does.
        self.display = self
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
