import asyncio
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

        self.execute_hook = MagicMock()
        self.execute_hook_blocking = AsyncMock(return_value=[])
        self._history_manager = MagicMock()
        self._snapshot_manager = MagicMock()
        self._message_queue = asyncio.Queue()
        self._pending_attachments = []
        self._is_thinking = False
        self._running_llm_task = None
        self._background_tasks = set()
        self._llm_task = MagicMock()
        self._llm_task.get_system_prompt.return_value = "mock system prompt"
        self._llm_task.llm_config.model = "mock-model"
        self._llm_task.llm_config.resolve_model.return_value = "mock-resolved-model"
        self.ctx = MagicMock()
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
    ui._message_queue.get_nowait()  # drain the enqueued job
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


# --- command dispatch with hooks --------------------------------------------
#
# Exercised through the public API only (`classify_input`, `dispatch_command`,
# `schedule_command`): the private chain, the module-level helpers, and the
# block-signal parsing are all covered transitively here. `execute_hook` /
# `execute_hook_blocking` are public collaborators stubbed on the mock UI.

from zrb.llm.hook.types import HookEvent  # noqa: E402


def _hook_result(**overrides):
    """A HookExecutionResult-shaped stub with neutral defaults."""
    r = MagicMock()
    r.blocked = False
    r.exit_code = 0
    r.decision = None
    r.permission_decision = None
    r.permission_decision_reason = None
    r.reason = None
    r.continue_execution = True
    for key, value in overrides.items():
        setattr(r, key, value)
    return r


def test_classify_input_routes_by_recognition_not_prefix(ui):
    # Toggles / argument commands / custom are recognized regardless of the
    # token's prefix — a user-configured ">" redirect is a command, not a chat.
    ui._redirect_output_commands = [">"]
    assert ui.classify_input("> ~/out.txt") == "command"
    # Run-while-thinking commands.
    assert ui.classify_input("/btw what's up") == "thinking_command"
    assert ui.classify_input("/yolo") == "thinking_command"
    # Exact-match toggle and argument command.
    assert ui.classify_input("/help") == "command"
    assert ui.classify_input("/save my-session") == "command"
    # Plain text — including text that merely starts with "/".
    assert ui.classify_input("hello world") == "message"
    assert ui.classify_input("/explain this code") == "message"
    assert ui.classify_input("   ") == "message"


def test_classify_input_recognizes_custom_command(ui):
    custom_cmd = MagicMock()
    custom_cmd.command = "/mycmd"
    custom_cmd.args = ["arg1"]
    custom_cmd.get_prompt.return_value = "prompt"
    ui._custom_commands = [custom_cmd]
    assert ui.classify_input("/mycmd arg") == "command"


@pytest.mark.asyncio
async def test_dispatch_fires_pre_and_post_when_handled(ui):
    # "/help" matches the info command, so a handler consumes it.
    await ui.dispatch_command("/help")

    pre_event = ui.execute_hook_blocking.call_args.args[0]
    assert pre_event == HookEvent.PRE_COMMAND
    assert ui.execute_hook_blocking.call_args.kwargs["command_name"] == "/help"

    post_event = ui.execute_hook.call_args.args[0]
    assert post_event == HookEvent.POST_COMMAND
    assert ui.execute_hook.call_args.kwargs["command_handled"] is True


@pytest.mark.asyncio
async def test_dispatch_passes_command_name_and_args(ui):
    # "/save my session" → name "/save", args "my session".
    await ui.dispatch_command("/save my session")

    kwargs = ui.execute_hook_blocking.call_args.kwargs
    assert kwargs["command_name"] == "/save"
    assert kwargs["command_args"] == "my session"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "blocking_result, expected_reason",
    [
        (_hook_result(blocked=True, exit_code=2, decision="block", reason="no"), "no"),
        (
            _hook_result(permission_decision="deny", permission_decision_reason="pol"),
            "pol",
        ),
        (_hook_result(continue_execution=False), "blocked by hook"),
    ],
)
async def test_dispatch_blocked_pre_cancels_command(
    ui, blocking_result, expected_reason
):
    # Each blocking signal (block / deny / continue=false) cancels dispatch.
    ui.execute_hook_blocking.return_value = [blocking_result]

    await ui.dispatch_command("/help")

    # Command never ran (help text absent), Post never fired, reason surfaced.
    assert not ui.execute_hook.called
    assert not any("Keyboard Shortcuts" in o for o in ui.outputs)
    assert any("⛔" in o and expected_reason in o for o in ui.outputs)


@pytest.mark.asyncio
async def test_dispatch_unhandled_forwards_to_llm(ui):
    await ui.dispatch_command("/notacommand here")

    # Recognized-as-routed but no handler consumed it → forwarded; no Post.
    assert ui.submitted_prompt == "/notacommand here"
    assert not ui.execute_hook.called


@pytest.mark.asyncio
async def test_dispatch_thinking_gates_command(ui):
    # While thinking, a non-thinking command (/help) is gated by the chain,
    # treated as unhandled, and neither submitted nor Post-fired.
    ui._is_thinking = True
    ui.submitted_prompt = None

    await ui.dispatch_command("/help")

    assert ui.submitted_prompt is None
    assert not ui.execute_hook.called
    assert not any("Keyboard Shortcuts" in o for o in ui.outputs)


@pytest.mark.asyncio
async def test_schedule_command_runs_dispatch_as_task(ui):
    captured = {}

    async def fake_dispatch(text, *, guarded=True):
        captured["text"] = text

    ui.dispatch_command = fake_dispatch

    ui.schedule_command("/help")

    # A background task was registered; awaiting it runs the dispatch.
    assert len(ui._background_tasks) == 1
    await list(ui._background_tasks)[0]
    assert captured["text"] == "/help"


@pytest.mark.asyncio
async def test_schedule_rejects_concurrent_command(ui):
    # First command is scheduled but has not run yet (still in sync code).
    ui.schedule_command("/help")
    # A second command while the first is in flight is rejected, not raced.
    ui.schedule_command("/exit")

    assert len(ui._background_tasks) == 1
    assert any("already running" in o for o in ui.outputs)

    # Once the first finishes, a new command is accepted again.
    await list(ui._background_tasks)[0]
    ui.outputs.clear()
    ui.schedule_command("/help")
    assert len(ui._background_tasks) == 1
    assert not any("already running" in o for o in ui.outputs)
    await list(ui._background_tasks)[0]


@pytest.mark.asyncio
async def test_thinking_command_bypasses_inflight_guard(ui):
    calls = []

    async def fake_dispatch(text, *, guarded=True):
        calls.append((text, guarded))

    ui.dispatch_command = fake_dispatch

    ui.schedule_command("/help")  # guarded → in flight
    # A run-while-thinking command still schedules — not blocked by the guard.
    ui.schedule_command("/btw hi", guarded=False)

    assert len(ui._background_tasks) == 2
    assert not any("already running" in o for o in ui.outputs)
    for task in list(ui._background_tasks):
        await task
    assert ("/help", True) in calls
    assert ("/btw hi", False) in calls


@pytest.mark.asyncio
async def test_classify_and_dispatch_agree(ui):
    # classify_input and the dispatch chain both derive from _command_table,
    # so a token classified "command" is actually consumed (Post fires).
    assert ui.classify_input("/help") == "command"
    await ui.dispatch_command("/help")
    assert ui.execute_hook.call_args.args[0] == HookEvent.POST_COMMAND


@pytest.mark.asyncio
async def test_command_dispatch_exception_is_logged(ui):
    ui.execute_hook_blocking = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("zrb.llm.ui.base.commands_mixin.logger") as mock_logger:
        ui.schedule_command("/help")
        task = list(ui._background_tasks)[0]
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0)  # let the done-callback run

    assert mock_logger.error.called

    # The in-flight flag was cleared despite the exception — next command runs.
    ui.execute_hook_blocking = AsyncMock(return_value=[])
    ui.schedule_command("/help")
    assert len(ui._background_tasks) == 1
    await list(ui._background_tasks)[0]
