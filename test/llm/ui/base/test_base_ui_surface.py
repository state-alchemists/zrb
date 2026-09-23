"""Public state-property surface of `BaseUI`.

A wall of small getter/setter properties (model slots, task handles, cwd,
plan mode, ...) sits in the middle of `BaseUI`. Keybindings and `MultiUI`
write through them, so they are pinned here: each reads back what it was
given, and the composed-part delegators forward to the part we assert on.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.ui.base.message_queue import QueuedMessage
from zrb.llm.ui.base.ui import BaseUI


class _SurfaceUI(BaseUI):
    def __init__(self, **kwargs):
        self.outputs = []
        super().__init__(**kwargs)

    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        self.outputs.append(sep.join(str(v) for v in values))

    async def ask_user(self, prompt: str, agent_id: str | None = None) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0

    async def run_async(self) -> str:
        return self.last_output


@pytest.fixture
def surface_ui():
    return _SurfaceUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
    )


def _make_entry(text: str) -> QueuedMessage:
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind="message", run=run)


def test_state_properties_roundtrip(surface_ui):
    surface_ui.small_model = "small"
    assert surface_ui.small_model == "small"
    surface_ui.multimodal_model = "big"
    assert surface_ui.multimodal_model == "big"
    surface_ui.conversation_session_name = "session-x"
    assert surface_ui.conversation_session_name == "session-x"

    surface_ui.running_llm_task = None
    assert surface_ui.running_llm_task is None
    surface_ui.cwd = "/tmp"
    assert surface_ui.cwd == "/tmp"
    surface_ui.git_info = "main"
    assert surface_ui.git_info == "main"
    assert surface_ui.markdown_theme is None
    surface_ui.process_messages_task = None
    assert surface_ui.process_messages_task is None
    surface_ui.trigger_tasks = []
    assert surface_ui.trigger_tasks == []
    surface_ui.system_info_task = None
    assert surface_ui.system_info_task is None

    assert surface_ui.snapshot_manager is None
    assert surface_ui.background_tasks == set()
    assert surface_ui.pending_attachments == []
    surface_ui.plan_mode_active = True
    assert surface_ui.plan_mode_active is True
    surface_ui.plan_mode_active = False
    assert surface_ui.plan_mode_active is False
    surface_ui.last_result_data = "answer"
    assert surface_ui.last_result_data == "answer"
    assert surface_ui.ctx is not None
    assert surface_ui.commands is not None


def test_command_alias_lists_read_from_config(surface_ui):
    assert surface_ui.exit_commands == surface_ui.exit_commands
    assert surface_ui.info_commands
    assert surface_ui.save_commands
    assert surface_ui.load_commands
    assert surface_ui.attach_commands
    assert surface_ui.photo_commands
    assert surface_ui.redirect_output_commands
    assert surface_ui.yolo_toggle_commands
    assert surface_ui.set_model_commands
    assert surface_ui.btw_commands
    assert surface_ui.plan_commands
    assert surface_ui.voice_commands
    assert surface_ui.rewind_commands
    assert surface_ui.copy_commands


def test_classify_input_routes_plain_text_as_message(surface_ui):
    assert surface_ui.classify_input("hello there") == "message"
    assert surface_ui.classify_input("   ") == "message"
    assert surface_ui.handle_toggle_voice("garbage") is False


@pytest.mark.asyncio
async def test_ask_user_choice_forwards_formatted_spec(surface_ui):
    with patch(
        "zrb.llm.ui.base.ui.format_choice_spec", return_value="FORMATTED"
    ) as fmt:
        answer = await surface_ui.ask_user_choice(MagicMock())
    assert answer == "yes"
    fmt.assert_called_once()


@pytest.mark.asyncio
async def test_schedule_command_runs_dispatch_as_background(surface_ui):
    with patch.object(
        surface_ui, "dispatch_command", new_callable=AsyncMock
    ) as dispatch:
        surface_ui.schedule_command("hello")
        await asyncio.sleep(0.02)
    dispatch.assert_awaited_once_with("hello", guarded=True)


@pytest.mark.asyncio
async def test_dispatch_command_forwards_unhandled_text_to_queue(surface_ui):
    await surface_ui.dispatch_command("hello there")


def test_submit_attachment_forwards_path(surface_ui, tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("payload")
    surface_ui.submit_attachment(str(target))
    assert target.exists()


def test_edit_queued_message_logs_child_redraw_failure(surface_ui):
    class _BombRedrawUI(_SurfaceUI):
        def redraw_echo(self, entry):
            raise RuntimeError("splice failed")

    child = _BombRedrawUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
    )
    parent = MagicMock()
    parent.children = [child]
    surface_ui.multi_ui_parent = parent
    entry = _make_entry("old text")
    surface_ui.effective_message_queue.add(entry)
    assert surface_ui.edit_queued_message(entry, "  new text  ") is True
    assert entry.text == "new text"
