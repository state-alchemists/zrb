"""Tests for agent common utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _route_hooks(mapping):
    """An execute_hooks mock that returns per-event HookExecutionResult lists."""

    async def _execute(event, data, *args, **kwargs):
        return mapping.get(event, [])

    return AsyncMock(side_effect=_execute)


@pytest.mark.asyncio
async def test_call_tool_pretooluse_deny_blocks():
    """A PreToolUse hook returning permissionDecision="deny" blocks the call and
    the underlying tool never runs."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.executor import HookExecutionResult
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    deny = HookExecutionResult(
        success=True, permission_decision="deny", permission_decision_reason="nope"
    )
    with (
        patch(
            "zrb.llm.hook.manager.hook_manager.execute_hooks",
            _route_hooks({HookEvent.PRE_TOOL_USE: [deny]}),
        ),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
        ) as mock_super,
    ):
        res = await wrapped_ts.call_tool("t", {"a": 1}, None, None)

    assert isinstance(res, ToolReturn)
    assert res.metadata.get("blocked") is True
    assert "nope" in str(res.return_value)
    mock_super.assert_not_called()


@pytest.mark.asyncio
async def test_call_tool_pretooluse_updated_input_rewrites_args():
    """A PreToolUse hook returning updatedInput rewrites the args passed to the
    underlying tool."""
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.executor import HookExecutionResult
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    rewrite = HookExecutionResult(success=True, updated_input={"a": 99})
    with (
        patch(
            "zrb.llm.hook.manager.hook_manager.execute_hooks",
            _route_hooks({HookEvent.PRE_TOOL_USE: [rewrite]}),
        ),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
        ) as mock_super,
    ):
        mock_super.return_value = "ok"
        await wrapped_ts.call_tool("t", {"a": 1}, None, None)

    assert mock_super.call_args.args[1] == {"a": 99}


@pytest.mark.asyncio
async def test_call_tool_pretooluse_skipped_when_approved():
    """PreToolUse does not fire in call_tool when the call already went through
    the deferred-approval path (ctx.tool_call_approved=True) — no double-fire."""
    from types import SimpleNamespace

    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    execute = _route_hooks({})
    ctx = SimpleNamespace(tool_call_approved=True, tool_call_id="c1")
    with (
        patch("zrb.llm.hook.manager.hook_manager.execute_hooks", execute),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
        ) as mock_super,
    ):
        mock_super.return_value = "ok"
        await wrapped_ts.call_tool("t", {"a": 1}, ctx, None)

    fired = [c.args[0] for c in execute.call_args_list]
    assert HookEvent.PRE_TOOL_USE not in fired
    assert HookEvent.POST_TOOL_USE in fired


@pytest.mark.asyncio
async def test_call_tool_posttooluse_block():
    """A PostToolUse hook with decision="block" discards the tool result."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.executor import HookExecutionResult
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    block = HookExecutionResult(success=True, decision="block", reason="bad output")
    with (
        patch(
            "zrb.llm.hook.manager.hook_manager.execute_hooks",
            _route_hooks({HookEvent.POST_TOOL_USE: [block]}),
        ),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
        ) as mock_super,
    ):
        mock_super.return_value = "secret"
        res = await wrapped_ts.call_tool("t", {}, None, None)

    assert isinstance(res, ToolReturn)
    assert res.metadata.get("blocked") is True
    assert "bad output" in str(res.return_value)


@pytest.mark.asyncio
async def test_call_tool_posttooluse_updated_output_replaces_content():
    """A PostToolUse hook with updatedToolOutput replaces what the model reads."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.executor import HookExecutionResult
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    transform = HookExecutionResult(
        success=True, hook_specific_output={"updatedToolOutput": "REDACTED"}
    )
    with (
        patch(
            "zrb.llm.hook.manager.hook_manager.execute_hooks",
            _route_hooks({HookEvent.POST_TOOL_USE: [transform]}),
        ),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
        ) as mock_super,
    ):
        mock_super.return_value = "original"
        res = await wrapped_ts.call_tool("t", {}, None, None)

    assert isinstance(res, ToolReturn)
    assert res.return_value == "REDACTED"
    assert res.content is None


@pytest.mark.asyncio
async def test_call_tool_posttooluse_additional_context_appended():
    """A PostToolUse hook's additionalContext is appended to the model-facing
    output (Claude injects it into context after the tool result)."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.executor import HookExecutionResult
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    add_ctx = HookExecutionResult(
        success=True,
        hook_specific_output={"additionalContext": "note: linter passed"},
    )
    with (
        patch(
            "zrb.llm.hook.manager.hook_manager.execute_hooks",
            _route_hooks({HookEvent.POST_TOOL_USE: [add_ctx]}),
        ),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
        ) as mock_super,
    ):
        mock_super.return_value = "original"
        res = await wrapped_ts.call_tool("t", {}, None, None)

    assert isinstance(res, ToolReturn)
    assert res.return_value == "original\n\nnote: linter passed"
    assert res.content is None


@pytest.mark.asyncio
async def test_call_tool_posttooluse_failure_fires_on_exception():
    """When the underlying tool raises, PostToolUseFailure fires and a safe
    error ToolReturn is surfaced."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    execute = _route_hooks({})
    with (
        patch("zrb.llm.hook.manager.hook_manager.execute_hooks", execute),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool",
            side_effect=ValueError("boom"),
        ),
    ):
        res = await wrapped_ts.call_tool("t", {"a": 1}, None, None)

    assert isinstance(res, ToolReturn)
    assert res.metadata.get("error") is True
    fired = [c.args[0] for c in execute.call_args_list]
    assert HookEvent.POST_TOOL_USE_FAILURE in fired


@pytest.mark.asyncio
async def test_call_tool_appends_override_note_when_args_were_edited():
    """A tool call whose arguments the user edited during approval gets a
    `[SYSTEM NOTE]` appended to its result, so the model learns what actually
    ran instead of silently reading a mismatched result (override_registry,
    see docs/adr/adr-0085.md)."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.tool_call.override_registry import record_override

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    record_override("edited-call", {"path": "a.txt"}, {"path": "b.txt"})
    ctx = MagicMock(tool_call_id="edited-call")
    with patch(
        "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
    ) as mock_super:
        mock_super.return_value = "ok"
        res = await wrapped_ts.call_tool("t", {"path": "b.txt"}, ctx, None)

    assert isinstance(res, ToolReturn)
    assert "ok" in res.return_value
    assert "[SYSTEM NOTE]" in res.return_value
    assert "b.txt" in res.return_value
