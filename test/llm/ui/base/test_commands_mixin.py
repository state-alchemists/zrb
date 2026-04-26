import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.base.commands_mixin import CommandsMixin


class MockUI(CommandsMixin):
    def __init__(self):
        self._exit_commands = ["/exit"]
        self._info_commands = ["/help"]
        self._save_commands = ["/save"]
        self._load_commands = ["/load"]
        self._rewind_commands = ["/rewind"]
        self._redirect_output_commands = ["/redirect"]
        self._attach_commands = ["/attach"]
        self._yolo_toggle_commands = ["/yolo"]
        self._set_model_commands = ["/model"]
        self._exec_commands = ["/exec"]
        self._btw_commands = ["/btw"]
        self._summarize_commands = ["/summarize"]
        self._custom_commands = []

        self._history_manager = MagicMock()
        self._snapshot_manager = MagicMock()
        self._message_queue = asyncio.Queue()
        self._pending_attachments = []
        self._is_thinking = False
        self._running_llm_task = None
        self._background_tasks = set()
        self._llm_task = MagicMock()
        self._model = "test-model"
        self._conversation_session_name = "default"
        self._markdown_theme = None
        self.last_output = "some ai output"
        self.yolo = False

        self.outputs = []
        self.exited = False

    def append_to_output(self, text, end="\n"):
        self.outputs.append(str(text) + end)

    def invalidate_ui(self):
        pass

    def on_exit(self):
        self.exited = True

    async def _update_system_info(self):
        pass

    def _get_output_field_width(self):
        return 80

    def _submit_user_message(self, task, prompt):
        self.submitted_prompt = prompt


@pytest.fixture
def ui():
    return MockUI()


def test_handle_exit_command(ui):
    assert ui._handle_exit_command("/exit") is True
    assert ui.exited is True
    assert ui._handle_exit_command("hello") is False


def test_handle_info_command(ui):
    assert ui._handle_info_command("/help") is True
    assert any("Available Commands" in o for o in ui.outputs)


def test_handle_save_command(ui):
    ui._history_manager.load.return_value = ["msg1"]
    assert ui._handle_save_command("/save my-session") is True
    ui._history_manager.update.assert_called_with("my-session", ["msg1"])
    ui._history_manager.save.assert_called_with("my-session")
    assert "saved" in "".join(ui.outputs)


def test_handle_load_command(ui):
    ui._history_manager.load.return_value = []
    assert ui._handle_load_command("/load other-session") is True
    assert ui._conversation_session_name == "other-session"
    assert "switched" in "".join(ui.outputs)


def test_handle_rewind_command_list(ui):
    snap = MagicMock()
    snap.sha = "1234567890"
    snap.timestamp = "2021-01-01"
    snap.label = "test"
    ui._snapshot_manager.list_snapshots.return_value = [snap]

    assert ui._handle_rewind_command("/rewind") is True
    assert "12345678" in "".join(ui.outputs)


@pytest.mark.asyncio
async def test_handle_rewind_command_restore(ui):
    snap = MagicMock()
    snap.sha = "1234567890"
    snap.message_count = 5
    ui._snapshot_manager.list_snapshots.return_value = [snap]
    ui._snapshot_manager.restore_snapshot = AsyncMock(return_value=True)

    assert ui._handle_rewind_command("/rewind 1") is True
    # Restoration happens in a background task
    assert len(ui._background_tasks) == 1
    task = list(ui._background_tasks)[0]
    await task
    ui._snapshot_manager.restore_snapshot.assert_called_with(snap.sha)


def test_handle_redirect_command(ui, tmp_path):
    out_file = tmp_path / "output.txt"
    assert ui._handle_redirect_command(f"/redirect {out_file}") is True
    assert out_file.read_text() == "some ai output"
    assert "redirected" in "".join(ui.outputs)


def test_handle_attach_command(ui, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    assert ui._handle_attach_command(f"/attach {f}") is True
    assert str(f) in ui._pending_attachments


def test_toggle_yolo(ui):
    ui.toggle_yolo()
    assert ui.yolo is True
    ui.toggle_yolo()
    assert ui.yolo is False


def test_handle_toggle_yolo_selective(ui):
    assert ui._handle_toggle_yolo("/yolo Write,Edit") is True
    assert ui.yolo == frozenset(["Write", "Edit"])


def test_handle_set_model_command(ui):
    assert ui._handle_set_model_command("/model gpt-4") is True
    assert ui._model == "gpt-4"
    assert "switched" in "".join(ui.outputs)


@pytest.mark.asyncio
async def test_handle_exec_command(ui):
    assert ui._handle_exec_command("/exec echo hello") is True
    job = ui._message_queue.get_nowait()
    with patch("asyncio.create_subprocess_shell") as mock_sub:
        mock_proc = AsyncMock()
        mock_proc.stdout.readline.side_effect = [b"hello\n", b""]
        mock_proc.stderr.readline.return_value = b""
        mock_proc.wait.return_value = 0
        mock_sub.return_value = mock_proc

        await ui._run_shell_command("echo hello")
        assert "hello" in "".join(ui.outputs)
        assert "successfully" in "".join(ui.outputs)


@pytest.mark.asyncio
async def test_handle_btw_command(ui):
    with patch("pydantic_ai.Agent") as mock_agent_cls:
        mock_agent = mock_agent_cls.return_value
        mock_agent.run = AsyncMock()
        mock_agent.run.return_value = MagicMock(output="btw answer")
        ui._history_manager.load.return_value = []

        assert ui._handle_btw_command("/btw what time is it?") is True
        assert len(ui._background_tasks) == 1
        task = list(ui._background_tasks)[0]
        await task
        assert "btw answer" in "".join(ui.outputs)


def test_handle_custom_command(ui):
    custom_cmd = MagicMock()
    custom_cmd.command = "/mycmd"
    custom_cmd.args = ["arg1"]
    custom_cmd.get_prompt.return_value = "custom prompt"
    ui._custom_commands = [custom_cmd]

    assert ui._handle_custom_command("/mycmd val1") is True
    assert ui.submitted_prompt == "custom prompt"
    custom_cmd.get_prompt.assert_called_with({"arg1": "val1"})
