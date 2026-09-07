"""Shared `BaseUI` stand-in for the `llm/ui/base` command tests.

`MockUI` holds the state `BaseUICommands` and its conversation/model/exec
parts read through `self._base_ui`, composes a real `BaseUICommands`, and
forwards attribute lookups to it and its parts, so a test can call any
handler as `ui.handle_<x>_command(...)`.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.ui.base.commands import BaseUICommands


class MockUI:
    """Stand-in for `BaseUI`: owns the state `BaseUICommands` and its
    conversation/model/exec collaborators read through `self._base_ui`,
    plus the `BaseUI` methods they call (`append_to_output`, `on_exit`, ...).
    Composes a real `BaseUICommands(self)` and forwards attribute
    lookups to it (and its sub-collaborators) so the many existing
    `ui.handle_*`/`ui.classify_input`/... call sites below keep working
    unchanged."""

    def __init__(self):
        self.exit_commands = ["/exit"]
        self.info_commands = ["/help"]
        self.save_commands = ["/save"]
        self.load_commands = ["/load"]
        self.rewind_commands = ["/rewind"]
        self.redirect_output_commands = ["/redirect"]
        self.attach_commands = ["/attach"]
        self.photo_commands = ["/photo"]
        self.yolo_toggle_commands = ["/yolo"]
        self.set_model_commands = ["/model"]
        self.exec_commands = ["/exec"]
        self.btw_commands = ["/btw"]
        self.plan_commands = ["/plan"]
        self.summarize_commands = ["/summarize"]
        self.copy_commands = []
        self.voice_commands = ["/voice"]
        self.voice_mode_active = False
        self.voice_recording_active = False
        self.voice_task = None
        self.voice_stop_event = None
        self.custom_commands = []

        self.execute_hook = MagicMock()
        self.execute_hook_blocking = AsyncMock(return_value=[])
        self.history_manager = MagicMock()
        self.replay_history = MagicMock()
        self.reset_session_token_usage = MagicMock()
        self.original_persona_snapshot = None
        self.active_subagent_persona = None
        self.snapshot_manager = MagicMock()
        self.message_queue = asyncio.Queue()
        self.pending_attachments = []
        self.is_thinking = False
        self.running_llm_task = None
        self.background_tasks = set()
        self.llm_task = MagicMock()
        self.llm_task.get_system_prompt.return_value = "mock system prompt"
        self.llm_task.llm_config.model = "mock-model"
        self.llm_task.llm_config.resolve_model.return_value = "mock-resolved-model"
        self.ctx = MagicMock()
        self.model = "test-model"
        self.conversation_session_name = "default"
        self.markdown_theme = None
        self.last_output = "some ai output"
        self.yolo = False
        self.plan_mode_active = False

        self.outputs = []
        self.exited = False

        self._cmds = BaseUICommands(self)

    def __getattr__(self, name):
        cmds = self.__dict__.get("_cmds")
        if cmds is None:
            raise AttributeError(name)
        for collaborator_attr in ("", "conversation", "models", "exec"):
            holder = getattr(cmds, collaborator_attr) if collaborator_attr else cmds
            if hasattr(holder, name):
                return getattr(holder, name)
        raise AttributeError(name)

    def append_to_output(self, text, end="\n"):
        self.outputs.append(str(text) + end)

    def append_markdown(self, markdown_text):
        self.append_to_output(markdown_text)

    def invalidate_ui(self):
        pass

    def on_exit(self):
        self.exited = True

    async def update_system_info(self):
        pass

    def _get_output_field_width(self):
        return 80

    def submit_message(self, prompt):
        self.submitted_prompt = prompt


@pytest.fixture
def ui():
    return MockUI()
