import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    r.data = {}
    for key, value in overrides.items():
        setattr(r, key, value)
    return r


@pytest.mark.asyncio
async def test_run_shell_command_reports_nonzero_exit(ui, tmp_path):
    """A failing command surfaces its exit code instead of 'successfully'."""
    await ui.run_shell_command(f"exit 3")
    assert "Command failed with exit code 3" in "".join(ui.outputs)
    assert ui.is_thinking is False


@pytest.mark.asyncio
async def test_run_shell_command_reports_spawn_error(ui):
    with patch("asyncio.create_subprocess_shell", side_effect=OSError("no shell")):
        await ui.run_shell_command("echo hi")
    assert "[Error: no shell]" in "".join(ui.outputs)


@pytest.mark.asyncio
async def test_handle_btw_command_empty_question(ui):
    assert ui.handle_btw_command("/btw  ") is False
    assert len(ui.background_tasks) == 0


@pytest.mark.asyncio
async def test_stream_btw_response_strips_system_prompt_from_history(ui):
    """The btw agent must not inherit the main agent's system prompt parts."""
    from pydantic_ai.messages import ModelRequest, SystemPromptPart, UserPromptPart

    dirty_history = [
        ModelRequest(
            parts=[SystemPromptPart(content="main persona"), UserPromptPart("hi")]
        ),
        "not-a-model-request",
    ]
    ui.history_manager.load.return_value = dirty_history
    seen = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            pass

        async def run(self, question, message_history=None, **kwargs):
            seen["history"] = message_history
            return MagicMock(output="side answer")

    with patch("pydantic_ai.Agent", FakeAgent):
        await ui.stream_btw_response(ui.llm_task, "quick question")

    cleaned = seen["history"]
    # SystemPromptPart removed; the user part and non-ModelRequest items stay.
    request_entries = [m for m in cleaned if isinstance(m, ModelRequest)]
    assert len(request_entries) == 1
    assert all(not isinstance(p, SystemPromptPart) for p in request_entries[0].parts)
    assert "not-a-model-request" in cleaned
    assert "side answer" in "".join(ui.outputs)


@pytest.mark.asyncio
async def test_stream_btw_response_survives_agent_failure(ui):
    class ExplodingAgent:
        def __init__(self, **kwargs):
            pass

        async def run(self, question, message_history=None):
            raise RuntimeError("provider down")

    ui.history_manager.load.return_value = []
    with patch("pydantic_ai.Agent", ExplodingAgent):
        await ui.stream_btw_response(ui.llm_task, "q")
    assert "[Error: provider down]" in "".join(ui.outputs)


def test_handle_custom_command_ignored_while_thinking_or_blank(ui):
    custom_cmd = MagicMock()
    custom_cmd.command = "/mycmd"
    ui.custom_commands = [custom_cmd]

    ui.is_thinking = True
    assert ui.handle_custom_command("/mycmd x") is False
    ui.is_thinking = False
    assert ui.handle_custom_command("   ") is False


@pytest.mark.asyncio
async def test_handle_btw_command(ui):
    with patch("pydantic_ai.Agent") as mock_agent_cls:
        mock_agent = mock_agent_cls.return_value
        mock_agent.run = AsyncMock()
        mock_agent.run.return_value = MagicMock(output="btw answer")
        ui.history_manager.load.return_value = []

        assert ui.handle_btw_command("/btw what time is it?") is True
        assert len(ui.background_tasks) == 1
        task = list(ui.background_tasks)[0]
        await task
        assert "btw answer" in "".join(ui.outputs)


def test_handle_custom_command(ui):
    custom_cmd = MagicMock()
    custom_cmd.command = "/mycmd"
    custom_cmd.args = ["arg1"]
    custom_cmd.get_prompt.return_value = "custom prompt"
    ui.custom_commands = [custom_cmd]

    assert ui.handle_custom_command("/mycmd val1") is True
    assert ui.submitted_prompt == "custom prompt"
    custom_cmd.get_prompt.assert_called_with({"arg1": "val1"})


def test_classify_input_routes_by_recognition_not_prefix(ui):
    # Toggles / argument commands / custom are recognized regardless of the
    # token's prefix — a user-configured ">" redirect is a command, not a chat.
    ui.redirect_output_commands = [">"]
    assert ui.classify_input("> ~/out.txt") == "command"
    # Run-while-thinking commands.
    assert ui.classify_input("/btw what's up") == "thinking_command"
    assert ui.classify_input("/yolo") == "thinking_command"
    # Selective yolo (/yolo Write,Edit) must also route as a command, not chat.
    assert ui.classify_input("/yolo Write,Edit") == "thinking_command"
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
    ui.custom_commands = [custom_cmd]
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
async def test_precommand_hook_rewrites_command_args(ui):
    # A PreCommand hook overrides command_args → "/model opus" runs as
    # "/model sonnet" (the token is preserved, the argument swapped).
    ui.execute_hook_blocking.return_value = [
        _hook_result(data={"command_args": "sonnet"})
    ]

    await ui.dispatch_command("/model opus")

    assert ui.model == "sonnet"  # the rewritten model was applied
    # PostCommand reflects the rewritten argument, not the original.
    assert ui.execute_hook.call_args.kwargs["command_args"] == "sonnet"


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
    ui.is_thinking = True
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
    assert len(ui.background_tasks) == 1
    await list(ui.background_tasks)[0]
    assert captured["text"] == "/help"


@pytest.mark.asyncio
async def test_schedule_rejects_concurrent_command(ui):
    # First command is scheduled but has not run yet (still in sync code).
    ui.schedule_command("/help")
    # A second command while the first is in flight is rejected, not raced.
    ui.schedule_command("/exit")

    assert len(ui.background_tasks) == 1
    assert any("already running" in o for o in ui.outputs)

    # Once the first finishes, a new command is accepted again.
    await list(ui.background_tasks)[0]
    ui.outputs.clear()
    ui.schedule_command("/help")
    assert len(ui.background_tasks) == 1
    assert not any("already running" in o for o in ui.outputs)
    await list(ui.background_tasks)[0]


@pytest.mark.asyncio
async def test_thinking_command_bypasses_inflight_guard(ui):
    calls = []

    async def fake_dispatch(text, *, guarded=True):
        calls.append((text, guarded))

    ui.dispatch_command = fake_dispatch

    ui.schedule_command("/help")  # guarded → in flight
    # A run-while-thinking command still schedules — not blocked by the guard.
    ui.schedule_command("/btw hi", guarded=False)

    assert len(ui.background_tasks) == 2
    assert not any("already running" in o for o in ui.outputs)
    for task in list(ui.background_tasks):
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

    with patch("zrb.llm.ui.base.commands.logger") as mock_logger:
        ui.schedule_command("/help")
        task = list(ui.background_tasks)[0]
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0)  # let the done-callback run

    assert mock_logger.error.called

    # The in-flight flag was cleared despite the exception — next command runs.
    ui.execute_hook_blocking = AsyncMock(return_value=[])
    ui.schedule_command("/help")
    assert len(ui.background_tasks) == 1
    await list(ui.background_tasks)[0]


def test_handle_toggle_voice_enables(ui):
    """`/voice` toggles voice mode on when disabled."""
    with patch.dict(os.environ, {"ZRB_LLM_VOICE_ENABLED": "true"}):
        assert ui.voice_mode_active is False
        result = ui.handle_toggle_voice("/voice")
        assert result is True
        assert ui.voice_mode_active is True
        assert any("ON" in o for o in ui.outputs)


def test_handle_toggle_voice_disables(ui):
    """`/voice` toggles voice mode off when enabled."""
    ui.voice_mode_active = True
    with patch.dict(os.environ, {"ZRB_LLM_VOICE_ENABLED": "true"}):
        result = ui.handle_toggle_voice("/voice")
        assert result is True
        assert ui.voice_mode_active is False
        assert any("OFF" in o for o in ui.outputs)


def test_handle_toggle_voice_blocked_when_disabled(ui):
    """`/voice` shows a message when voice is not enabled in config."""
    with patch.dict(os.environ, {"ZRB_LLM_VOICE_ENABLED": "false"}):
        result = ui.handle_toggle_voice("/voice")
        assert result is True
        assert ui.voice_mode_active is False
        assert any("not enabled" in o for o in ui.outputs)


def test_handle_toggle_voice_auto_enables_when_vosk_installed(ui):
    """Untouched `LLM_VOICE_ENABLED` + vosk installed → voice just works."""
    env = {k: v for k, v in os.environ.items() if not k.endswith("_LLM_VOICE_ENABLED")}
    with patch.dict(os.environ, env, clear=True):
        with patch("zrb.llm.voice.engine.vosk_installed", return_value=True):
            result = ui.handle_toggle_voice("/voice")
    assert result is True
    assert ui.voice_mode_active is True
    assert any("vosk detected" in o for o in ui.outputs)
