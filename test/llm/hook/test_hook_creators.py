import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.hook.hook_creators import (
    create_agent_hook,
    create_command_hook,
    create_prompt_hook,
)
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.schema import (
    AgentHookConfig,
    CommandHookConfig,
    PromptHookConfig,
)
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


@pytest.mark.asyncio
async def test_command_hook_injects_event_and_field_env_vars():
    """Context fields and event data are exported to the hook's environment."""
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
    # dict-valued fields are JSON-encoded
    assert '{"file": "x.py"}' in out
    assert '{"k": "v"}' in out


@pytest.mark.asyncio
async def test_command_hook_remote_metadata_sets_env():
    """metadata['remote'] flips CLAUDE_CODE_REMOTE to 'true'."""
    hook = create_command_hook(CommandHookConfig(command='echo "$CLAUDE_CODE_REMOTE"'))
    context = HookContext(
        event=HookEvent.NOTIFICATION,
        event_data=None,
        metadata={"remote": True},
    )

    result = await hook(context)

    assert (result.output or "").strip() == "true"


@pytest.mark.asyncio
async def test_command_hook_none_event_data_serializes_null():
    """When event_data is None, CLAUDE_EVENT_DATA is the literal 'null'."""
    hook = create_command_hook(CommandHookConfig(command='echo "$CLAUDE_EVENT_DATA"'))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data=None)

    result = await hook(context)

    assert (result.output or "").strip() == "null"


@pytest.mark.asyncio
async def test_command_hook_non_serializable_event_data_falls_back_to_str():
    """Non-JSON-serializable event_data falls back to its string repr in env,
    and the stdin payload degrades to a minimal event-only object."""
    hook = create_command_hook(CommandHookConfig(command='echo "$CLAUDE_EVENT_DATA"'))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={1, 2, 3})

    result = await hook(context)

    # set() is not JSON serializable -> str() fallback; output is non-empty.
    assert result.success is True
    assert (result.output or "").strip() != ""
    assert "null" not in (result.output or "")


@pytest.mark.asyncio
async def test_command_hook_expands_working_dir(tmp_path):
    """config.working_dir is expanded and used as the subprocess cwd."""
    hook = create_command_hook(
        CommandHookConfig(command="pwd", working_dir=str(tmp_path))
    )
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    result = await hook(context)

    # macOS /var -> /private/var symlinks could differ; compare basenames.
    import os

    assert os.path.basename((result.output or "").strip()) == tmp_path.name


@pytest.mark.asyncio
async def test_command_hook_missing_working_dir_is_ignored(tmp_path):
    """A non-existent working_dir is dropped (hook inherits the parent cwd)."""
    missing = str(tmp_path / "does-not-exist")
    hook = create_command_hook(
        CommandHookConfig(command="echo ok", working_dir=missing)
    )
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    result = await hook(context)

    assert result.success is True
    assert (result.output or "").strip() == "ok"


@pytest.mark.asyncio
async def test_command_hook_generic_failure_logs_error(caplog):
    """A non-zero, non-2, non-signal exit is an error with stderr appended."""
    hook = create_command_hook(CommandHookConfig(command='echo "boom" >&2; exit 3'))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with caplog.at_level(logging.ERROR, logger="zrb.llm.hook.hook_creators"):
        result = await hook(context)

    assert result.success is False
    assert "exit code 3" in (result.output or "")
    assert "boom" in (result.output or "")
    assert [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.asyncio
async def test_command_hook_outer_exception_is_caught(caplog):
    """An unexpected error while spawning the subprocess is caught and returned
    as a failed HookResult."""
    hook = create_command_hook(CommandHookConfig(command="echo hi"))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with patch(
        "zrb.llm.hook.hook_creators.subprocess.Popen",
        side_effect=OSError("spawn failed"),
    ):
        with caplog.at_level(logging.ERROR, logger="zrb.llm.hook.hook_creators"):
            result = await hook(context)

    assert result.success is False
    assert "spawn failed" in (result.output or "")


@pytest.mark.asyncio
async def test_command_hook_non_serializable_stdin_falls_back_to_minimal():
    """When to_claude_json() carries a non-serializable value (here a set in
    tool_input), the stdin payload degrades to an event-only object and the
    hook still runs."""
    hook = create_command_hook(
        CommandHookConfig(
            command="python3 -c 'import sys,json; "
            'print(json.load(sys.stdin)["hook_event_name"])\''
        )
    )
    # permission_suggestions is a list field: env-injection uses str() on it (so
    # it passes the env step), but it's part of to_claude_json(), and a set
    # inside it makes json.dumps fail -> stdin minimal-payload fallback.
    context = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        event_data=None,
        permission_suggestions=[{"weird": {1, 2}}],
    )

    result = await hook(context)

    assert result.success is True
    assert "PreToolUse" in (result.output or "")


@pytest.mark.asyncio
async def test_command_hook_error_exit_with_stdout_only(caplog):
    """A non-zero exit with stdout (no stderr) appends stdout to the error."""
    hook = create_command_hook(
        CommandHookConfig(command='echo "info on stdout"; exit 4')
    )
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with caplog.at_level(logging.ERROR, logger="zrb.llm.hook.hook_creators"):
        result = await hook(context)

    assert result.success is False
    assert "exit code 4" in (result.output or "")
    assert "info on stdout" in (result.output or "")


@pytest.mark.asyncio
async def test_command_hook_timeout_process_already_gone():
    """If the timed-out process is already gone (ProcessLookupError on kill),
    the timeout path still returns cleanly."""
    hook = create_command_hook(CommandHookConfig(command="sleep 5"), timeout=0.05)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    class _Proc:
        returncode = None

        def communicate(self, input=None):
            import time as _t

            _t.sleep(5)
            return b"", b""

        def kill(self):
            raise ProcessLookupError()

        def wait(self):
            return 0

    with patch("zrb.llm.hook.hook_creators.subprocess.Popen", return_value=_Proc()):
        result = await hook(context)

    assert result.success is False
    assert "timed out" in (result.output or "")


@pytest.mark.asyncio
async def test_command_hook_cancelled_kills_process():
    """Cancelling the awaiting task kills the subprocess and re-raises."""
    import asyncio as _asyncio

    killed = {"done": False}

    class _Proc:
        returncode = None

        def communicate(self, input=None):
            import time as _t

            _t.sleep(5)
            return b"", b""

        def kill(self):
            killed["done"] = True

        def wait(self):
            return 0

    hook = create_command_hook(CommandHookConfig(command="sleep 5"))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with patch("zrb.llm.hook.hook_creators.subprocess.Popen", return_value=_Proc()):
        task = _asyncio.ensure_future(hook(context))
        await _asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(_asyncio.CancelledError):
            await task

    assert killed["done"] is True


@pytest.mark.asyncio
async def test_command_hook_cancelled_when_process_already_gone():
    """If the subprocess is already gone when cancellation fires, the
    ProcessLookupError on kill is swallowed and CancelledError still propagates."""
    import asyncio as _asyncio

    class _Proc:
        returncode = None

        def communicate(self, input=None):
            import time as _t

            _t.sleep(5)
            return b"", b""

        def kill(self):
            raise ProcessLookupError()

        def wait(self):
            return 0

    hook = create_command_hook(CommandHookConfig(command="sleep 5"))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with patch("zrb.llm.hook.hook_creators.subprocess.Popen", return_value=_Proc()):
        task = _asyncio.ensure_future(hook(context))
        await _asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(_asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_command_hook_unknown_signal_number_uses_generic_label():
    """A negative returncode that isn't a known signal number falls back to a
    generic 'signal N' label rather than raising."""

    class _Proc:
        returncode = -99  # 99 is not a valid signal -> ValueError fallback

        def communicate(self, input=None):
            return b"", b""

        def kill(self):
            pass

        def wait(self):
            return 0

    hook = create_command_hook(CommandHookConfig(command="true"))
    context = HookContext(event=HookEvent.SESSION_END, event_data={})

    with patch("zrb.llm.hook.hook_creators.subprocess.Popen", return_value=_Proc()):
        result = await hook(context)

    assert result.success is False
    assert "signal 99" in (result.output or "")


@pytest.mark.asyncio
async def test_command_hook_exit0_json_modifications_respected():
    """On exit 0 a JSON stdout object becomes the modifications dict."""
    hook = create_command_hook(
        CommandHookConfig(command='echo \'{"hookSpecificOutput": {"a": 1}}\'')
    )
    context = HookContext(event=HookEvent.POST_TOOL_USE, event_data={})

    result = await hook(context)

    assert result.success is True
    assert result.modifications == {"hookSpecificOutput": {"a": 1}}


# --- Prompt hook ---------------------------------------------------------


def _agent_returning(output):
    """Build a patchable pydantic_ai.Agent whose run() returns `output`."""
    agent_instance = MagicMock()
    agent_instance.run = AsyncMock(return_value=MagicMock(output=output))
    agent_cls = MagicMock(return_value=agent_instance)
    return agent_cls


@pytest.mark.asyncio
async def test_prompt_hook_no_model_configured():
    """With no model on the config and CFG.LLM_MODEL empty, the hook fails fast."""
    config = PromptHookConfig(user_prompt_template="hi", model=None)
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    with patch("zrb.llm.hook.hook_creators.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = ""
        result = await hook(context)

    assert result.success is False
    assert "No LLM model" in (result.output or "")


@pytest.mark.asyncio
async def test_prompt_hook_plain_output_success():
    """A plain (non-JSON) agent output is returned with empty modifications, and
    the user_prompt_template placeholders are substituted from context fields."""
    config = PromptHookConfig(
        user_prompt_template="Prompt was: {{prompt}}", model="fake-model"
    )
    hook = create_prompt_hook(config)
    context = HookContext(
        event=HookEvent.USER_PROMPT_SUBMIT, event_data={}, prompt="do it"
    )

    agent_cls = _agent_returning("plain answer")
    with (
        patch("zrb.llm.hook.hook_creators.llm_config") as mock_llm_config,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.output == "plain answer"
    assert result.modifications == {}
    # Verify template substitution actually happened.
    called_prompt = agent_cls.return_value.run.call_args.args[0]
    assert called_prompt == "Prompt was: do it"


@pytest.mark.asyncio
async def test_prompt_hook_json_output_becomes_modifications():
    """A JSON-object agent output is parsed into modifications."""
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    agent_cls = _agent_returning('{"decision": "block"}')
    with (
        patch("zrb.llm.hook.hook_creators.llm_config") as mock_llm_config,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {"decision": "block"}


@pytest.mark.asyncio
async def test_prompt_hook_malformed_json_output_stays_plain():
    """Output that looks like JSON ({...}) but doesn't parse keeps empty
    modifications instead of raising."""
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    agent_cls = _agent_returning("{not valid json}")
    with (
        patch("zrb.llm.hook.hook_creators.llm_config") as mock_llm_config,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {}


@pytest.mark.asyncio
async def test_prompt_hook_exception_returns_failure():
    """An error while running the agent is caught and returned as failure."""
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    with (
        patch("zrb.llm.hook.hook_creators.llm_config") as mock_llm_config,
        patch.dict(
            "sys.modules",
            {
                "pydantic_ai": MagicMock(
                    Agent=MagicMock(side_effect=RuntimeError("nope"))
                )
            },
        ),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is False
    assert "nope" in (result.output or "")


# --- Agent hook ----------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_hook_no_model_configured():
    config = AgentHookConfig(system_prompt="sp", model=None)
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with patch("zrb.llm.hook.hook_creators.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = ""
        result = await hook(context)

    assert result.success is False
    assert "No LLM model" in (result.output or "")


@pytest.mark.asyncio
async def test_agent_hook_uses_dict_event_data_and_returns_json():
    """A dict event_data drives the agent input; a JSON output is parsed."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={"a": 1})

    agent_cls = _agent_returning('{"ok": true}')
    with (
        patch("zrb.llm.hook.hook_creators.llm_config") as mock_llm_config,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {"ok": True}
    assert agent_cls.return_value.run.call_args.args[0] == "{'a': 1}"


@pytest.mark.asyncio
async def test_agent_hook_falls_back_to_event_value_when_no_input():
    """With no event_data and no prompt, the agent input is the event label."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.SESSION_START, event_data=None)

    agent_cls = _agent_returning("plain")
    with (
        patch("zrb.llm.hook.hook_creators.llm_config") as mock_llm_config,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {}
    user_input = agent_cls.return_value.run.call_args.args[0]
    assert HookEvent.SESSION_START.value in user_input


@pytest.mark.asyncio
async def test_agent_hook_uses_prompt_when_event_data_absent():
    """With no event_data but a prompt set, the prompt becomes the agent input."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(
        event=HookEvent.USER_PROMPT_SUBMIT, event_data=None, prompt="use me"
    )

    agent_cls = _agent_returning("plain")
    with (
        patch("zrb.llm.hook.hook_creators.llm_config") as mock_llm_config,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        await hook(context)

    assert agent_cls.return_value.run.call_args.args[0] == "use me"


@pytest.mark.asyncio
async def test_agent_hook_non_dict_event_data_stringified():
    """A non-dict, non-empty event_data is stringified for the agent input."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data="raw-text")

    agent_cls = _agent_returning("plain")
    with (
        patch("zrb.llm.hook.hook_creators.llm_config") as mock_llm_config,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert agent_cls.return_value.run.call_args.args[0] == "raw-text"


@pytest.mark.asyncio
async def test_agent_hook_malformed_json_output_stays_plain():
    """Agent output that looks like JSON but doesn't parse keeps empty
    modifications."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={"a": 1})

    agent_cls = _agent_returning("{bad json}")
    with (
        patch("zrb.llm.hook.hook_creators.llm_config") as mock_llm_config,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {}


@pytest.mark.asyncio
async def test_agent_hook_exception_returns_failure():
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={"a": 1})

    with (
        patch("zrb.llm.hook.hook_creators.llm_config") as mock_llm_config,
        patch.dict(
            "sys.modules",
            {
                "pydantic_ai": MagicMock(
                    Agent=MagicMock(side_effect=RuntimeError("boom"))
                )
            },
        ),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is False
    assert "boom" in (result.output or "")
