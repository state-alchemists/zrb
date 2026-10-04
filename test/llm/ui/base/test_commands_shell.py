import asyncio
import os
import re
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.hook.types import HookEvent  # noqa: E402
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.ui.base.commands import BaseUICommands


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


@pytest.mark.skipif(os.name != "posix", reason="`&` and `$!` are POSIX shell syntax")
@pytest.mark.asyncio
async def test_run_shell_command_ends_with_everything_it_started(ui):
    """`/exec server &` returns once the shell exits, though the child holds
    the pipes, and stops that child rather than leaving it running."""
    await asyncio.wait_for(ui.run_shell_command("sleep 30 & echo $!"), timeout=5)
    output = "".join(ui.outputs)
    child = int(re.search(r"^(\d+)$", output, re.MULTILINE).group(1))
    assert "Command finished successfully" in output
    assert await _wait_until_gone(child)


@pytest.mark.asyncio
async def test_run_shell_command_reports_spawn_error(ui):
    with patch("asyncio.create_subprocess_shell", side_effect=OSError("no shell")):
        await ui.run_shell_command("echo hi")
    assert "[Error: OSError: no shell]" in "".join(ui.outputs)


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
async def test_stream_btw_response_uses_the_tool_less_prompt(ui):
    """The side agent is told it has no tools, and is never handed the main
    agent's prompt — whose tool rules describe capabilities it lacks."""
    ui.history_manager.load.return_value = []
    ui.llm_task.get_system_prompt.side_effect = AssertionError("main prompt used")
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(return_value=MagicMock(output="side answer"))

    with patch("zrb.llm.agent.create_agent", return_value=fake_agent) as create:
        await ui.stream_btw_response(ui.llm_task, "quick question")

    kwargs = create.call_args.kwargs
    assert kwargs["system_prompt"] == get_prompt("side_question")
    assert not kwargs.get("tools")
    assert not kwargs.get("toolsets")


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
    assert "[Error: RuntimeError: provider down]" in "".join(ui.outputs)


def test_handle_custom_command_ignored_while_thinking_or_blank(ui):
    custom_cmd = MagicMock()
    custom_cmd.command = "/mycmd"
    custom_cmd.args = []
    custom_cmd.can_run_while_thinking = False
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
    custom_cmd.handle.return_value = None
    ui.custom_commands = [custom_cmd]

    assert ui.handle_custom_command("/mycmd val1") is True
    assert ui.submitted_prompt == "custom prompt"
    custom_cmd.get_prompt.assert_called_with({"arg1": "val1"})


def test_handle_action_command_shows_reply_without_prompting(ui):
    from zrb.llm.custom_command import ActionCommand

    calls = []
    ui.custom_commands = [
        ActionCommand("/toggle", lambda kwargs, ui: calls.append(kwargs) or "Toggled")
    ]
    ui.submitted_prompt = None

    assert ui.handle_custom_command("/toggle") is True
    assert calls == [{}]
    assert ui.submitted_prompt is None
    assert "Toggled" in "".join(ui.outputs)


def test_classify_input_routes_action_command_without_running_it(ui):
    from zrb.llm.custom_command import ActionCommand

    calls = []
    ui.custom_commands = [ActionCommand("/toggle", lambda kwargs, ui: calls.append(1))]

    assert ui.classify_input("/toggle") == "command"
    assert calls == []


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
    custom_cmd.can_run_while_thinking = False
    ui.custom_commands = [custom_cmd]
    assert ui.classify_input("/mycmd arg") == "command"


def test_command_that_can_run_while_thinking_runs_mid_turn(ui):
    from zrb.llm.custom_command import ActionCommand

    calls = []
    ui.custom_commands = [
        ActionCommand(
            "/mute", lambda kwargs, ui: calls.append(1), can_run_while_thinking=True
        )
    ]
    ui.is_thinking = True

    assert ui.classify_input("/mute") == "thinking_command"
    assert ui.handle_custom_command("/mute") is True
    assert calls == [1]


def test_action_command_receives_the_ui(ui):
    from zrb.llm.custom_command import ActionCommand

    seen = []
    ui.custom_commands = [ActionCommand("/who", lambda kwargs, got: seen.append(got))]

    ui.handle_custom_command("/who")
    assert seen == [ui]


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


@pytest.mark.skipif(os.name != "posix", reason="`$$` and `exec` are POSIX shell syntax")
@pytest.mark.asyncio
async def test_run_shell_command_stops_the_command_when_output_fails(ui):
    """A failing output write ends the read, and must end the command too."""
    pids = []
    write_output = ui.append_to_output

    def failing_append(text, end="\n"):
        if text.strip().isdigit():
            pids.append(int(text))
            raise RuntimeError("output broke")
        write_output(text, end=end)

    ui.append_to_output = failing_append
    await asyncio.wait_for(ui.run_shell_command("echo $$; exec sleep 30"), timeout=5)

    assert "output broke" in "".join(ui.outputs)
    assert await _wait_until_gone(pids[0])


async def _wait_until_gone(pid: int, timeout: float = 3) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        await asyncio.sleep(0.05)
    os.kill(pid, signal.SIGKILL)
    return False
