import logging

import pytest

from zrb.llm.hook.hook_creators import create_command_hook
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.schema import CommandHookConfig
from zrb.llm.hook.types import HookEvent


@pytest.mark.asyncio
async def test_command_hook_timeout_returns_clean_result():
    """A command hook that exceeds its timeout must be killed and reaped
    cleanly, returning a timeout HookResult.

    Regression: the kill path used ``await process.wait()`` on a sync
    ``subprocess.Popen``, whose ``.wait()`` returns an int — ``await``-ing it
    raised ``TypeError: 'int' object can't be awaited``, which swallowed the
    TimeoutError and left the subprocess unreaped.
    """
    hook = create_command_hook(CommandHookConfig(command="sleep 5"), timeout=0.1)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    result = await hook(context)

    assert result.success is False
    assert "timed out" in (result.output or "")
    # The bug surfaced as this message via the outer exception handler.
    assert "can't be awaited" not in (result.output or "")


@pytest.mark.asyncio
async def test_command_hook_killed_by_signal_is_quiet_non_failure(caplog):
    """A hook subprocess killed by a signal (POSIX returns -N) is interrupt/
    teardown — e.g. the terminal delivering SIGINT (-2) on Ctrl+C to the whole
    process group — not a hook bug. It must NOT log an error.

    Regression: a normal Ctrl+C during `zrb chat` surfaced as a scary
    `ERROR: Command hook failed: Command failed with exit code -2`.
    """
    # The shell kills itself with SIGINT, so Popen.returncode is -2.
    hook = create_command_hook(CommandHookConfig(command="kill -INT $$"))
    context = HookContext(event=HookEvent.SESSION_END, event_data={})

    with caplog.at_level(logging.DEBUG, logger="zrb.llm.hook.hook_creators"):
        result = await hook(context)

    assert result.success is False
    assert "SIGINT" in (result.output or "")
    # Crucially, no ERROR was emitted for a normal interrupt.
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.asyncio
async def test_command_hook_stdout_becomes_context_for_session_start():
    """Claude-compatible: a SessionStart hook's plain stdout is injected as
    additionalContext (so a simple `echo` hook works like in Claude Code)."""
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
    """Plain stdout is NOT injected for events Claude doesn't treat that way."""
    hook = create_command_hook(CommandHookConfig(command="echo noise"))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    result = await hook(context)

    assert "additionalContext" not in result.modifications


@pytest.mark.asyncio
async def test_command_hook_json_stdout_respected_over_raw_context():
    """A SessionStart hook emitting a JSON control object keeps it verbatim; the
    raw-stdout fallback only applies to unstructured output."""
    hook = create_command_hook(CommandHookConfig(command='echo \'{"foo": "bar"}\''))
    context = HookContext(event=HookEvent.SESSION_START, event_data={})

    result = await hook(context)

    assert result.modifications == {"foo": "bar"}


@pytest.mark.asyncio
async def test_command_hook_exit2_reason_from_stderr():
    """Claude-compatible: on exit 2 the block reason is read from stderr."""
    hook = create_command_hook(
        CommandHookConfig(command='echo "denied by policy" >&2; exit 2')
    )
    context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={})

    result = await hook(context)

    assert result.success is False
    assert result.should_stop is True
    assert result.modifications.get("reason") == "denied by policy"


@pytest.mark.asyncio
async def test_command_hook_exit2_reason_from_stdout_plain_text():
    """Legacy zrb behavior: a plain-stdout reason on exit 2 still works."""
    hook = create_command_hook(
        CommandHookConfig(command='echo "stdout reason"; exit 2')
    )
    context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={})

    result = await hook(context)

    assert result.modifications.get("reason") == "stdout reason"


@pytest.mark.asyncio
async def test_command_hook_exit2_json_reason_wins_over_stderr():
    """An explicit `reason` in a stdout JSON control object takes precedence."""
    hook = create_command_hook(
        CommandHookConfig(
            command='echo "stderr text" >&2; echo \'{"reason": "json wins"}\'; exit 2'
        )
    )
    context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={})

    result = await hook(context)

    assert result.modifications.get("reason") == "json wins"


@pytest.mark.asyncio
async def test_command_hook_exit2_json_without_reason_keeps_default():
    """A JSON control object with no reason and no stderr keeps the default."""
    hook = create_command_hook(
        CommandHookConfig(command='echo \'{"decision": "block"}\'; exit 2')
    )
    context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={})

    result = await hook(context)

    assert result.modifications.get("reason") == "Blocked by hook"
