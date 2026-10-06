'Command-hook behavior and exit-code semantics.'

import logging
import os
import signal
from unittest.mock import patch

import pytest

from zrb.llm.hook.creator import create_command_hook
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.schema import CommandHookConfig
from zrb.llm.hook.types import HookEvent


posix_shell_only = pytest.mark.skipif(
    os.name != "posix",
    reason="drives a POSIX shell script; cmd.exe does not share the syntax",
)




@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_killed_by_signal_is_quiet_non_failure(caplog):
    'A signal-terminated hook is not logged as an error.'

    previous_handler = signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        hook = create_command_hook(CommandHookConfig(command="kill -INT $$"))
        context = HookContext(event=HookEvent.SESSION_END, event_data={})

        with caplog.at_level(logging.DEBUG, logger="zrb.llm.hook.creator"):
            result = await hook(context)
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    assert result.success is False
    assert "SIGINT" in (result.output or "")
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.asyncio
async def test_command_hook_unknown_signal_number_uses_generic_label():
    "A negative returncode that isn't a known signal number falls back to a"

    class _Proc:
        returncode = -99

        stdin = stdout = stderr = None

        def poll(self):
            return -99

        def kill(self):
            pass

        def wait(self):
            return -99

        def communicate(self, input=None):


            return b"", b""

    hook = create_command_hook(CommandHookConfig(command="true"))
    context = HookContext(event=HookEvent.SESSION_END, event_data={})

    with patch("zrb.llm.hook.creator.subprocess.Popen", return_value=_Proc()):
        result = await hook(context)

    assert result.success is False
    assert "signal 99" in (result.output or "")


@pytest.mark.asyncio
async def test_command_hook_stdout_becomes_context_for_session_start():
    "Claude-compatible: a SessionStart hook's plain stdout is injected as"
    hook = create_command_hook(CommandHookConfig(command="echo hello-context"))
    context = HookContext(event=HookEvent.SESSION_START, event_data={})

    result = await hook(context)

    assert result.success is True
    assert result.modifications.get("additionalContext") == "hello-context"


@pytest.mark.asyncio
async def test_command_hook_stdout_becomes_context_for_user_prompt_submit():
    hook = create_command_hook(CommandHookConfig(command="echo extra"))
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    result = await hook(context)

    assert result.modifications.get("additionalContext") == "extra"


@pytest.mark.asyncio
async def test_command_hook_stdout_not_context_for_other_events():
    "Plain stdout is NOT injected for events Claude doesn't treat that way."
    hook = create_command_hook(CommandHookConfig(command="echo noise"))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    result = await hook(context)

    assert "additionalContext" not in result.modifications


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_json_stdout_respected_over_raw_context():
    'A SessionStart hook emitting a JSON control object keeps it verbatim; the'
    hook = create_command_hook(CommandHookConfig(command='echo \'{"foo": "bar"}\''))
    context = HookContext(event=HookEvent.SESSION_START, event_data={})

    result = await hook(context)

    assert result.modifications == {"foo": "bar"}


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_exit0_json_modifications_respected():
    'On exit 0 a JSON stdout object becomes the modifications dict.'
    hook = create_command_hook(
        CommandHookConfig(command='echo \'{"hookSpecificOutput": {"a": 1}}\'')
    )
    context = HookContext(event=HookEvent.POST_TOOL_USE, event_data={})

    result = await hook(context)

    assert result.success is True
    assert result.modifications == {"hookSpecificOutput": {"a": 1}}


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_exit2_reason_from_stderr():
    'Claude-compatible: on exit 2 the block reason is read from stderr.'
    hook = create_command_hook(
        CommandHookConfig(command='echo "denied by policy" >&2; exit 2')
    )
    context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={})

    result = await hook(context)

    assert result.success is False
    assert result.should_stop is True
    assert result.modifications.get("reason") == "denied by policy"


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_exit2_reason_from_stdout_plain_text():
    'Legacy zrb behavior: a plain-stdout reason on exit 2 still works.'
    hook = create_command_hook(
        CommandHookConfig(command='echo "stdout reason"; exit 2')
    )
    context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={})

    result = await hook(context)

    assert result.modifications.get("reason") == "stdout reason"


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_exit2_json_reason_wins_over_stderr():
    'An explicit `reason` in a stdout JSON control object takes precedence.'
    hook = create_command_hook(
        CommandHookConfig(
            command='echo "stderr text" >&2; echo \'{"reason": "json wins"}\'; exit 2'
        )
    )
    context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={})

    result = await hook(context)

    assert result.modifications.get("reason") == "json wins"


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_exit2_json_without_reason_keeps_default():
    'A JSON control object with no reason and no stderr keeps the default.'
    hook = create_command_hook(
        CommandHookConfig(command='echo \'{"decision": "block"}\'; exit 2')
    )
    context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={})

    result = await hook(context)

    assert result.modifications.get("reason") == "Blocked by hook"


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_generic_failure_logs_error(caplog):
    'A non-zero, non-2, non-signal exit is an error with stderr appended.'
    hook = create_command_hook(CommandHookConfig(command='echo "boom" >&2; exit 3'))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with caplog.at_level(logging.ERROR, logger="zrb.llm.hook.creator"):
        result = await hook(context)

    assert result.success is False
    assert "exit code 3" in (result.output or "")
    assert "boom" in (result.output or "")
    assert [r for r in caplog.records if r.levelno >= logging.ERROR]


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_error_exit_with_stdout_only(caplog):
    'A non-zero exit with stdout (no stderr) appends stdout to the error.'
    hook = create_command_hook(
        CommandHookConfig(command='echo "info on stdout"; exit 4')
    )
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with caplog.at_level(logging.ERROR, logger="zrb.llm.hook.creator"):
        result = await hook(context)

    assert result.success is False
    assert "exit code 4" in (result.output or "")
    assert "info on stdout" in (result.output or "")





@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_injects_event_and_field_env_vars():
    "Context fields and event data are exported to the hook's environment."
    hook = create_command_hook(
        CommandHookConfig(
            command=(
                'echo "$CLAUDE_HOOK_EVENT|$CLAUDE_PROMPT|'
                '$CLAUDE_TOOL_INPUT|$CLAUDE_EVENT_DATA"'
            )
        )
    )
    context = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        event_data={"k": "v"},
        prompt="hello",
        tool_input={"file": "x.py"},
    )

    result = await hook(context)

    assert result.success is True
    out = result.output or ""
    assert "PreToolUse" in out
    assert "hello" in out

    assert '{"file": "x.py"}' in out
    assert '{"k": "v"}' in out


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_gets_response_text_when_event_data_is_too_large():
    'A Stop payload with real history overflows CLAUDE_EVENT_DATA and is'
    hook = create_command_hook(
        CommandHookConfig(
            command='echo "[$CLAUDE_EVENT_DATA]|$CLAUDE_LAST_ASSISTANT_MESSAGE"'
        )
    )
    context = HookContext(
        event=HookEvent.STOP,
        event_data={"output": "All tests pass.", "history": ["x" * 20000]},
        last_assistant_message="All tests pass.",
    )

    result = await hook(context)

    assert (result.output or "").strip() == "[]|All tests pass."


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_remote_metadata_sets_env():
    "metadata['remote'] flips CLAUDE_CODE_REMOTE to 'true'."
    hook = create_command_hook(CommandHookConfig(command='echo "$CLAUDE_CODE_REMOTE"'))
    context = HookContext(
        event=HookEvent.NOTIFICATION,
        event_data=None,
        metadata={"remote": True},
    )

    result = await hook(context)

    assert (result.output or "").strip() == "true"


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_sets_plugin_root_env_when_configured():
    'A hook config carrying `plugin_root` exports it as CLAUDE_PLUGIN_ROOT.'
    hook = create_command_hook(
        CommandHookConfig(
            command='echo "$CLAUDE_PLUGIN_ROOT"',
            plugin_root="/opt/some-plugin",
        )
    )
    context = HookContext(event=HookEvent.NOTIFICATION, event_data=None)

    result = await hook(context)

    assert (result.output or "").strip() == "/opt/some-plugin"


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_plugin_root_defaults_to_empty():
    'A hook with no recorded plugin origin gets an empty CLAUDE_PLUGIN_ROOT,'
    hook = create_command_hook(
        CommandHookConfig(command='echo "[$CLAUDE_PLUGIN_ROOT]"')
    )
    context = HookContext(event=HookEvent.NOTIFICATION, event_data=None)

    result = await hook(context)

    assert (result.output or "").strip() == "[]"


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_none_event_data_serializes_null():
    "When event_data is None, CLAUDE_EVENT_DATA is the literal 'null'."
    hook = create_command_hook(CommandHookConfig(command='echo "$CLAUDE_EVENT_DATA"'))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data=None)

    result = await hook(context)

    assert (result.output or "").strip() == "null"


@pytest.mark.asyncio
async def test_command_hook_non_serializable_event_data_falls_back_to_str():
    'Non-JSON-serializable event_data falls back to its string repr in env,'
    hook = create_command_hook(CommandHookConfig(command='echo "$CLAUDE_EVENT_DATA"'))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={1, 2, 3})

    result = await hook(context)


    assert result.success is True
    assert (result.output or "").strip() != ""
    assert "null" not in (result.output or "")


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_non_serializable_stdin_falls_back_to_minimal():
    'When to_claude_json() carries a non-serializable value (here a set in'
    hook = create_command_hook(
        CommandHookConfig(
            command="python3 -c 'import sys,json; "
            'print(json.load(sys.stdin)["hook_event_name"])\''
        )
    )



    context = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        event_data=None,
        permission_suggestions=[{"weird": {1, 2}}],
    )

    result = await hook(context)

    assert result.success is True
    assert "PreToolUse" in (result.output or "")





@pytest.mark.asyncio
async def test_command_hook_expands_working_dir(tmp_path):
    'config.working_dir is expanded and used as the subprocess cwd.'
    hook = create_command_hook(
        CommandHookConfig(command="pwd", working_dir=str(tmp_path))
    )
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    result = await hook(context)


    assert os.path.basename((result.output or "").strip()) == tmp_path.name


@pytest.mark.asyncio
async def test_command_hook_missing_working_dir_is_ignored(tmp_path):
    'A non-existent working_dir is dropped (hook inherits the parent cwd).'
    missing = str(tmp_path / "does-not-exist")
    hook = create_command_hook(
        CommandHookConfig(command="echo ok", working_dir=missing)
    )
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    result = await hook(context)

    assert result.success is True
    assert (result.output or "").strip() == "ok"
