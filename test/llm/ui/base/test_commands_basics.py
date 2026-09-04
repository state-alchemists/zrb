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
        for collaborator_attr in ("", "_conversation", "_models", "_exec"):
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


def test_handle_exit_command(ui):
    assert ui.handle_exit_command("/exit") is True
    assert ui.exited is True
    assert ui.handle_exit_command("hello") is False


def test_handle_info_command(ui):
    assert ui.handle_info_command("/help") is True
    assert any("Available Commands" in o for o in ui.outputs)


def test_handle_save_command(ui):
    ui.history_manager.load.return_value = ["msg1"]
    assert ui.handle_save_command("/save my-session") is True
    ui.history_manager.update.assert_called_with("my-session", ["msg1"])
    ui.history_manager.save.assert_called_with("my-session")
    assert "saved" in "".join(ui.outputs)


def test_handle_load_command(ui):
    ui.history_manager.load.return_value = []
    assert ui.handle_load_command("/load other-session") is True
    assert ui.conversation_session_name == "other-session"
    assert "switched" in "".join(ui.outputs)


@pytest.mark.asyncio
async def test_handle_rewind_command_list(ui):
    snap = MagicMock()
    snap.sha = "1234567890"
    snap.timestamp = "2021-01-01"
    snap.label = "test"
    ui.snapshot_manager.list_snapshots.return_value = [snap]

    assert ui.handle_rewind_command("/rewind") is True
    # Listing happens in a background task (git subprocess off the UI thread)
    assert len(ui.background_tasks) == 1
    task = list(ui.background_tasks)[0]
    await task
    assert "12345678" in "".join(ui.outputs)


@pytest.mark.asyncio
async def test_handle_rewind_command_restore(ui):
    snap = MagicMock()
    snap.sha = "1234567890"
    snap.message_count = 5
    ui.snapshot_manager.list_snapshots.return_value = [snap]
    ui.snapshot_manager.restore_snapshot = AsyncMock(return_value=True)

    assert ui.handle_rewind_command("/rewind 1") is True
    # Restoration happens in a background task
    assert len(ui.background_tasks) == 1
    task = list(ui.background_tasks)[0]
    await task
    ui.snapshot_manager.restore_snapshot.assert_called_with(snap.sha)


def test_handle_redirect_command(ui, tmp_path):
    out_file = tmp_path / "output.txt"
    assert ui.handle_redirect_command(f"/redirect {out_file}") is True
    assert out_file.read_text() == "some ai output"
    assert "redirected" in "".join(ui.outputs)


def test_handle_redirect_command_bare(ui):
    """Bare /redirect copies last_output to clipboard."""
    ui.redirect_output_commands = ["/redirect"]
    ui.last_output = "clipboard content"
    with patch("zrb.llm.util.clipboard.copy_text", return_value=True) as mock_copy:
        result = ui.handle_redirect_command("/redirect")

    assert result is True
    mock_copy.assert_called_once_with("clipboard content")


def test_handle_redirect_command_bare_falls_back_to_history(ui):
    """Bare /redirect uses the last history response when no live output exists.

    Reproduces `chat --session <name>`: history is replayed but last_output
    is empty until a live turn runs.
    """
    ui.redirect_output_commands = ["/redirect"]
    ui.last_output = ""
    ui.history_manager.load.return_value = [{"role": "assistant", "content": "x"}]
    with patch("zrb.llm.util.clipboard.copy_text", return_value=True) as mock_copy:
        with patch(
            "zrb.llm.util.history_formatter.extract_last_response_text",
            return_value="from history",
        ):
            result = ui.handle_redirect_command("/redirect")

    assert result is True
    mock_copy.assert_called_once_with("from history")


def test_handle_redirect_command_bare_no_output_no_history(ui):
    """Bare /redirect errors when neither live output nor history text exists."""
    ui.redirect_output_commands = ["/redirect"]
    ui.last_output = ""
    ui.history_manager.load.return_value = []
    with patch("zrb.llm.util.clipboard.copy_text") as mock_copy:
        with patch(
            "zrb.llm.util.history_formatter.extract_last_response_text",
            return_value="",
        ):
            result = ui.handle_redirect_command("/redirect")

    assert result is True
    mock_copy.assert_not_called()
    assert any("no ai response" in o.lower() for o in ui.outputs)


def test_handle_copy_command(ui):
    """Bare /copy copies full transcript to clipboard."""
    ui.copy_commands = ["/copy"]
    ui.history_manager.load.return_value = [{"role": "user", "content": "hi"}]

    with patch("zrb.llm.util.clipboard.copy_text", return_value=True) as mock_copy:
        with patch(
            "zrb.llm.util.history_formatter.format_history_as_text",
            return_value="copy text",
        ):
            result = ui.handle_copy_command("/copy")

    assert result is True
    mock_copy.assert_called_once_with("copy text")


def test_handle_copy_command_to_file(ui, tmp_path):
    """Copy with path writes transcript to file."""
    ui.copy_commands = ["/copy"]
    ui.history_manager.load.return_value = [{"role": "assistant", "content": "msg"}]
    out_file = tmp_path / "transcript.txt"

    with patch(
        "zrb.llm.util.history_formatter.format_history_as_text",
        return_value="file content",
    ):
        result = ui.handle_copy_command(f"/copy {out_file}")

    assert result is True
    assert out_file.read_text() == "file content"
    assert any("saved" in o.lower() for o in ui.outputs)


def test_handle_copy_command_no_history(ui):
    """Copy shows error when no history."""
    ui.copy_commands = ["/copy"]
    ui.history_manager.load.return_value = []

    result = ui.handle_copy_command("/copy")

    assert result is True
    assert any("no conversation" in o.lower() for o in ui.outputs)


def test_handle_attach_command(ui, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    assert ui.handle_attach_command(f"/attach {f}") is True
    assert str(f) in ui.pending_attachments


def test_handle_attach_command_not_found(ui, tmp_path):
    missing = tmp_path / "missing.txt"
    assert ui.handle_attach_command(f"/attach {missing}") is True
    assert ui.pending_attachments == []
    assert any("not found" in o.lower() for o in ui.outputs)


def test_handle_attach_command_directory(ui, tmp_path):
    assert ui.handle_attach_command(f"/attach {tmp_path}") is True
    assert ui.pending_attachments == []
    assert any("not found" in o.lower() for o in ui.outputs)


def test_handle_attach_command_unsupported_type(ui, tmp_path):
    f = tmp_path / "test.xyz"
    f.write_text("data")
    assert ui.handle_attach_command(f"/attach {f}") is True
    assert ui.pending_attachments == []
    assert any("unsupported file type" in o.lower() for o in ui.outputs)


def test_handle_attach_command_oversized(ui, tmp_path, monkeypatch):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 1)
    assert ui.handle_attach_command(f"/attach {f}") is True
    assert ui.pending_attachments == []
    assert any("too large" in o.lower() for o in ui.outputs)


@pytest.mark.asyncio
async def test_handle_photo_command_captures_and_attaches(ui):
    with patch(
        "zrb.llm.ui.base.conversation_commands.get_camera_photo",
        new=AsyncMock(return_value=b"\xff\xd8\xff-fake-jpeg"),
    ):
        assert ui.handle_photo_command("/photo") is True
        assert len(ui.background_tasks) == 1
        task = list(ui.background_tasks)[0]
        await task

    assert len(ui.pending_attachments) == 1
    assert any("photo captured" in o.lower() for o in ui.outputs)


@pytest.mark.asyncio
async def test_handle_photo_command_passes_device_argument(ui):
    mock_capture = AsyncMock(return_value=b"jpeg")
    with patch(
        "zrb.llm.ui.base.conversation_commands.get_camera_photo", new=mock_capture
    ):
        assert ui.handle_photo_command("/photo 1") is True
        task = list(ui.background_tasks)[0]
        await task

    mock_capture.assert_called_once_with("1")


@pytest.mark.asyncio
async def test_handle_photo_command_capture_failure(ui):
    with patch(
        "zrb.llm.ui.base.conversation_commands.get_camera_photo",
        new=AsyncMock(return_value=None),
    ):
        assert ui.handle_photo_command("/photo") is True
        task = list(ui.background_tasks)[0]
        await task

    assert ui.pending_attachments == []
    assert any("capture failed" in o.lower() for o in ui.outputs)


def test_handle_photo_command_ignores_unrelated_input(ui):
    assert ui.handle_photo_command("hello") is False


def test_handle_attach_command_already_attached(ui, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    ui.handle_attach_command(f"/attach {f}")
    ui.handle_attach_command(f"/attach {f}")
    assert ui.pending_attachments == [str(f)]
    assert any("already attached" in o.lower() for o in ui.outputs)


def test_toggle_yolo(ui):
    ui.toggle_yolo()
    assert ui.yolo is True
    ui.toggle_yolo()
    assert ui.yolo is False


def test_handle_toggle_yolo_selective(ui):
    assert ui.handle_toggle_yolo("/yolo Write,Edit") is True
    assert ui.yolo == frozenset(["Write", "Edit"])


def test_current_cycle_mode_reports_each_state(ui):
    assert ui.current_cycle_mode() == "normal"
    ui.yolo = frozenset(["Write", "Edit"])
    assert ui.current_cycle_mode() == "accept_edits"
    ui.yolo = frozenset(["Read", "Bash"])
    assert ui.current_cycle_mode() == "custom"
    ui.yolo = True
    assert ui.current_cycle_mode() == "yolo"
    ui.yolo = False
    ui.plan_mode_active = True
    # Plan takes precedence over any yolo value.
    ui.yolo = frozenset(["Write", "Edit"])
    assert ui.current_cycle_mode() == "plan"


def test_cycle_mode_advances_normal_to_edits_to_plan_to_normal(ui):
    ui.yolo = False
    ui.plan_mode_active = False
    assert ui.current_cycle_mode() == "normal"
    ui.cycle_mode()
    assert ui.current_cycle_mode() == "accept_edits"
    assert ui.yolo == frozenset(["Write", "Edit"])
    ui.cycle_mode()
    assert ui.current_cycle_mode() == "plan"
    assert ui.plan_mode_active is True
    assert ui.yolo is False  # plan and yolo never stack
    ui.cycle_mode()
    assert ui.current_cycle_mode() == "normal"
    assert ui.plan_mode_active is False
    assert ui.yolo is False


def test_cycle_mode_resets_off_cycle_yolo_into_cycle(ui):
    # Full yolo (set via Ctrl+Y / /yolo) is off-cycle; Shift+Tab resets to normal.
    ui.yolo = True
    ui.plan_mode_active = False
    ui.cycle_mode()
    assert ui.current_cycle_mode() == "normal"
    assert ui.yolo is False


def test_handle_set_model_command(ui):
    assert ui.handle_set_model_command("/model gpt-4") is True
    assert ui.model == "gpt-4"
    assert "switched" in "".join(ui.outputs)


def test_handle_set_model_command_small_variant(ui):
    assert ui.handle_set_model_command("/model small gpt-4o-mini") is True
    assert ui.small_model == "gpt-4o-mini"
    assert "Small model switched to: gpt-4o-mini" in "".join(ui.outputs)


def test_handle_set_model_command_multimodal_variant(ui):
    assert ui.handle_set_model_command("/model multimodal gemini-flash") is True
    assert ui.multimodal_model == "gemini-flash"
    assert "Multimodal model switched to: gemini-flash" in "".join(ui.outputs)


def test_handle_set_model_command_ignored_while_thinking(ui):
    ui.is_thinking = True
    assert ui.handle_set_model_command("/model gpt-5") is False
    assert ui.model == "test-model"


def test_handle_set_model_command_survives_prompt_manager_error(ui):
    """A prompt-manager failure is debug-logged; the switch itself still lands."""
    ui.llm_task = MagicMock()
    type(ui.llm_task).prompt_manager = PropertyMock(
        side_effect=RuntimeError("no manager")
    )
    assert ui.handle_set_model_command("/model gpt-4-turbo") is True
    assert ui.model == "gpt-4-turbo"


def test_handle_toggle_plan_command(ui):
    assert ui.handle_toggle_plan("/plan") is True
    assert ui.plan_mode_active is True
    assert "PLAN MODE: On" in "".join(ui.outputs)
    assert ui.handle_toggle_plan("/plan") is True
    assert ui.plan_mode_active is False
    assert "PLAN MODE: Off" in "".join(ui.outputs)


def test_handle_toggle_plan_command_unrelated_text(ui):
    assert ui.handle_toggle_plan("just a message") is False


def test_handle_yolo_selective_tools(ui):
    assert ui.handle_toggle_yolo("/yolo Write,Edit") is True
    assert ui.yolo == frozenset({"Write", "Edit"})
    # A tool list that parses to nothing leaves yolo untouched but still
    # consumes the input.
    ui.yolo = True
    assert ui.handle_toggle_yolo("/yolo ,") is True
    assert ui.yolo is True


@pytest.mark.asyncio
async def test_handle_exec_command(ui):
    assert ui.handle_exec_command("/exec echo hello") is True
    ui.message_queue.get_nowait()  # drain the enqueued job
    with patch("asyncio.create_subprocess_shell") as mock_sub:
        mock_proc = AsyncMock()
        mock_proc.stdout.readline.side_effect = [b"hello\n", b""]
        mock_proc.stderr.readline.return_value = b""
        mock_proc.wait.return_value = 0
        mock_sub.return_value = mock_proc

        await ui.run_shell_command("echo hello")
        assert "hello" in "".join(ui.outputs)
        assert "successfully" in "".join(ui.outputs)


def test_handle_exec_command_ignored_while_thinking(ui):
    ui.is_thinking = True
    assert ui.handle_exec_command("/exec echo hello") is False
