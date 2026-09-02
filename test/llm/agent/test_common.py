"""Tests for agent common utilities."""

import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.agent.common import create_safe_wrapper, safe_copy_result


def testsafe_copy_result_none():
    """Test safe_copy_result with None."""
    result = safe_copy_result(None)
    assert result is None


def testsafe_copy_result_string():
    """Test safe_copy_result with string."""
    result = safe_copy_result("test")
    assert result == "test"


def testsafe_copy_result_int():
    """Test safe_copy_result with int."""
    result = safe_copy_result(42)
    assert result == 42


def testsafe_copy_result_float():
    """Test safe_copy_result with float."""
    result = safe_copy_result(3.14)
    assert result == 3.14


def testsafe_copy_result_bool():
    """Test safe_copy_result with bool."""
    result = safe_copy_result(True)
    assert result is True


def testsafe_copy_result_list():
    """Test safe_copy_result makes a copy of list."""
    original = [1, 2, 3]
    result = safe_copy_result(original)
    assert result == [1, 2, 3]
    assert result is not original
    # Modify result, original should be unchanged
    result.append(4)
    assert original == [1, 2, 3]


def testsafe_copy_result_dict():
    """Test safe_copy_result makes a deep copy of dict."""
    original = {"key": "value", "nested": {"a": 1}}
    result = safe_copy_result(original)
    assert result == original
    assert result is not original
    # Modify result, original should be unchanged
    result["key"] = "modified"
    result["nested"]["a"] = 2
    assert original["key"] == "value"
    assert original["nested"]["a"] == 1


def testsafe_copy_result_set():
    """Test safe_copy_result makes a copy of set."""
    original = {1, 2, 3}
    result = safe_copy_result(original)
    assert result == {1, 2, 3}
    assert result is not original


def testsafe_copy_result_nested_list():
    """Test safe_copy_result with nested list."""
    original = [[1, 2], [3, 4]]
    result = safe_copy_result(original)
    assert result == [[1, 2], [3, 4]]
    # Modify nested element
    result[0].append(5)
    assert original == [[1, 2], [3, 4]]


def testsafe_copy_result_tuple():
    """Test safe_copy_result with tuple attempts deep copy."""
    original = (1, 2, 3)
    result = safe_copy_result(original)
    assert result == (1, 2, 3)


def testsafe_copy_result_object_with_deepcopy_failure():
    """Test safe_copy_result handles objects that can't be deep copied."""

    class NoDeepCopy:
        def __deepcopy__(self, memo):
            raise TypeError("Cannot deep copy")

        def __eq__(self, other):
            return isinstance(other, NoDeepCopy)

    obj = NoDeepCopy()
    result = safe_copy_result(obj)
    # Should return original when deepcopy fails
    assert result is obj


@pytest.mark.asyncio
async def testcreate_safe_wrapper_sync_function():
    """Test create_safe_wrapper with sync function."""

    def sync_func(x):
        return x * 2

    wrapped = create_safe_wrapper(sync_func)
    # The wrapper is async
    from pydantic_ai import ToolReturn

    result = await wrapped(5)
    assert isinstance(result, ToolReturn)
    assert result.return_value == 10
    assert result.content is None


@pytest.mark.asyncio
async def testcreate_safe_wrapper_async_function():
    """Test create_safe_wrapper with async function."""

    async def async_func(x):
        return x * 2

    wrapped = create_safe_wrapper(async_func)
    from pydantic_ai import ToolReturn

    result = await wrapped(5)
    assert isinstance(result, ToolReturn)
    assert result.return_value == 10


@pytest.mark.asyncio
async def testcreate_safe_wrapper_handles_exception():
    """Test create_safe_wrapper catches exceptions."""

    def failing_func():
        raise ValueError("Test error")

    wrapped = create_safe_wrapper(failing_func)
    from pydantic_ai import ToolReturn

    result = await wrapped()
    assert isinstance(result, ToolReturn)
    assert result.metadata.get("error") is True
    assert "Test error" in str(result.return_value)


@pytest.mark.asyncio
async def testcreate_safe_wrapper_sync_function_runs_off_event_loop():
    """Sync tools must not run inline on the event loop.

    The wrapper is a coroutine function, so pydantic-ai never applies its own
    executor offload — inline execution would freeze the TUI for the tool's
    duration (e.g. ReadFile on a large file).
    """
    import threading

    loop_thread = threading.current_thread()

    def sync_func():
        return threading.current_thread() is not loop_thread

    wrapped = create_safe_wrapper(sync_func)
    result = await wrapped()
    assert result.return_value is True


@pytest.mark.asyncio
async def testcreate_safe_wrapper_propagates_model_retry():
    """ModelRetry drives pydantic-ai's retry protocol — it must not be
    flattened into an error-string ToolReturn."""
    from pydantic_ai import ModelRetry

    def retrying_func():
        raise ModelRetry("try again with a narrower query")

    wrapped = create_safe_wrapper(retrying_func)
    with pytest.raises(ModelRetry):
        await wrapped()


@pytest.mark.asyncio
async def testcreate_safe_wrapper_already_tool_return():
    """Test create_safe_wrapper when function already returns ToolReturn."""
    from pydantic_ai import ToolReturn

    tr = ToolReturn(return_value="already_wrapped")

    async def wrapped_func():
        return tr

    wrapped = create_safe_wrapper(wrapped_func)
    result = await wrapped()
    assert result is tr


def test_wrap_tool_callable():
    """A bare callable is wrapped into a ``Tool`` (not left bare) so its
    capability tag survives into ``ToolDefinition.metadata``. The outer,
    per-call gate (``SafeToolsetWrapper.call_tool``) only ever sees a
    ``ToolsetTool``, which carries no ``.function`` and no arbitrary
    attributes — metadata is the only channel capability can reach it
    through (see ``zrb.llm.permission.capability_metadata``)."""
    from pydantic_ai import Tool

    from zrb.llm.agent.common import wrap_tool
    from zrb.llm.permission import Capability, tag

    def my_tool(x: int):
        return x

    tag(my_tool, Capability.READ)
    wrapped = wrap_tool(my_tool)
    assert isinstance(wrapped, Tool)
    assert wrapped.metadata == {"zrb_capability": Capability.READ}
    assert callable(wrapped.function)


def test_wrap_tool_instance():
    from pydantic_ai import Tool

    from zrb.llm.agent.common import wrap_tool
    from zrb.llm.permission import Capability, tag

    def my_tool(x: int):
        return x

    tag(my_tool, Capability.EDIT)
    tool_inst = Tool(
        my_tool, name="test", description="desc", metadata={"existing": True}
    )
    wrapped = wrap_tool(tool_inst)
    assert isinstance(wrapped, Tool)
    assert wrapped.name == "test"
    # The original tool's metadata is preserved, and the capability resolved
    # from the underlying tagged function is merged in.
    assert wrapped.metadata == {"existing": True, "zrb_capability": Capability.EDIT}


def test_wrap_tool_duck_typed_instance():
    """A tool object with ``.function`` that is not a pydantic-ai ``Tool``
    must still be rebuilt around the safe wrapper — returning it unchanged
    would drop error containment and the capability tag."""
    from pydantic_ai import Tool

    from zrb.llm.agent.common import wrap_tool
    from zrb.llm.permission import Capability, tag

    def my_tool(ctx, x: int):
        return x

    tag(my_tool, Capability.EXECUTE)

    class DuckTypedTool:
        function = staticmethod(my_tool)
        name = "duck"
        description = "duck-typed tool"
        takes_ctx = True
        metadata = {"custom": "kept"}

    wrapped = wrap_tool(DuckTypedTool())
    assert isinstance(wrapped, Tool)
    assert wrapped.name == "duck"
    assert wrapped.description == "duck-typed tool"
    assert wrapped.takes_ctx is True
    assert wrapped.metadata == {
        "custom": "kept",
        "zrb_capability": Capability.EXECUTE,
    }
    # The safe wrapper is in place: a raising call becomes an error
    # ToolReturn instead of an uncontained exception.
    import asyncio
    import inspect

    assert inspect.iscoroutinefunction(wrapped.function)

    def broken():
        raise RuntimeError("boom")

    broken_tool = DuckTypedTool()
    broken_tool.function = staticmethod(broken)
    broken_tool.name = "broken"
    result = asyncio.run(wrap_tool(broken_tool).function())
    assert "boom" in str(result)


@pytest.mark.asyncio
async def test_wrap_toolset():
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset

    ts = FunctionToolset(tools=[])
    wrapped_ts = wrap_toolset(ts)

    with patch(
        "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = "ok"
        # Test calling tool via wrapped toolset
        res = await wrapped_ts.call_tool("my_tool", {}, None, None)
        assert isinstance(res, ToolReturn)
        assert res.return_value == "ok"


@pytest.mark.asyncio
async def test_wrap_toolset_error():
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset

    async def failing_tool():
        raise ValueError("error")

    ts = FunctionToolset(tools=[failing_tool])
    wrapped_ts = wrap_toolset(ts)

    # Note: we need to pass a mock/real tool that will cause super().call_tool to fail
    # or just mock the super().call_tool.
    # Actually, the SafeToolsetWrapper.call_tool calls await super().call_tool

    with patch(
        "pydantic_ai.toolsets.WrapperToolset.call_tool", side_effect=ValueError("fail")
    ):
        res = await wrapped_ts.call_tool("any", {}, None, None)
        assert isinstance(res, ToolReturn)
        assert res.metadata["error"] is True


def _route_hooks(mapping):
    """An execute_hooks mock that returns per-event HookExecutionResult lists."""

    async def _execute(event, data, *args, **kwargs):
        return mapping.get(event, [])

    return AsyncMock(side_effect=_execute)


@pytest.mark.asyncio
async def test_apply_tool_result_limit_survives_none_metadata():
    """A raw ToolReturn with metadata=None (pydantic-ai's own default, e.g. from
    an MCP toolset), rewritten by a PostToolUse hook, must not crash the
    oversize/spill backstop. The rewritten content never went through a
    tool's own cap, so it is still routed through _apply_tool_result_limit,
    which merges new keys onto result.metadata."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.executor import HookExecutionResult
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    transform = HookExecutionResult(
        success=True, hook_specific_output={"updatedToolOutput": "z" * 500}
    )
    raw = ToolReturn(return_value="small", metadata=None)
    with (
        patch(
            "zrb.llm.hook.manager.hook_manager.execute_hooks",
            _route_hooks({HookEvent.POST_TOOL_USE: [transform]}),
        ),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool",
            new_callable=AsyncMock,
            return_value=raw,
        ),
        patch("zrb.llm.agent.common.CFG") as mock_cfg,
    ):
        mock_cfg.LLM_MAX_TOOL_RESULT_CHARS = 100
        res = await wrapped_ts.call_tool("external_tool", {}, None, None)

    assert isinstance(res, ToolReturn)
    assert res.metadata.get("oversized") is True


@pytest.mark.asyncio
async def test_call_tool_skips_backstop_for_untouched_self_framed_result():
    """A tool's own self-framed ToolReturn (e.g. Shell/Read after their own
    LLM_MAX_OUTPUT_CHARS truncation) is respected as-is when no PostToolUse
    hook rewrites it — even past LLM_MAX_TOOL_RESULT_CHARS. Re-running it
    through the global backstop would re-truncate an already-truncated result
    into a much smaller spill preview with no way to recover the true output.
    """
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    self_framed = ToolReturn(
        return_value="[TRUNCATED]..." + "z" * 200, metadata={"already": "framed"}
    )
    with (
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool",
            new_callable=AsyncMock,
            return_value=self_framed,
        ),
        patch("zrb.llm.agent.common.CFG") as mock_cfg,
    ):
        mock_cfg.LLM_MAX_TOOL_RESULT_CHARS = 10
        res = await wrapped_ts.call_tool("Read", {}, None, None)

    assert res is self_framed


@pytest.mark.asyncio
async def test_call_tool_backstop_still_applies_to_hook_rewritten_output():
    """A PostToolUse hook's updatedToolOutput is content that never went
    through the tool's own cap, so it must still be subject to the global
    LLM_MAX_TOOL_RESULT_CHARS backstop even when the pre-hook result was a
    self-framed ToolReturn."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.executor import HookExecutionResult
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    transform = HookExecutionResult(
        success=True, hook_specific_output={"updatedToolOutput": "z" * 500}
    )
    self_framed = ToolReturn(return_value="small")
    with (
        patch(
            "zrb.llm.hook.manager.hook_manager.execute_hooks",
            _route_hooks({HookEvent.POST_TOOL_USE: [transform]}),
        ),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool",
            new_callable=AsyncMock,
            return_value=self_framed,
        ),
        patch("zrb.llm.agent.common.CFG") as mock_cfg,
    ):
        mock_cfg.LLM_MAX_TOOL_RESULT_CHARS = 100
        res = await wrapped_ts.call_tool("t", {}, None, None)

    assert isinstance(res, ToolReturn)
    assert res.return_value == "z" * 500
    assert res.metadata.get("oversized") is True
    assert res.metadata.get("original_chars") == 500


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


@pytest.mark.asyncio
async def test_call_tool_override_note_is_one_shot_and_reaches_error_results():
    """The note is consumed once per call, and still reaches the model when
    the (edited) call fails."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.tool_call.override_registry import record_override

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    record_override("edited-call-2", {"path": "a.txt"}, {"path": "b.txt"})
    ctx = MagicMock(tool_call_id="edited-call-2")
    with patch(
        "pydantic_ai.toolsets.WrapperToolset.call_tool",
        side_effect=ValueError("boom"),
    ):
        res = await wrapped_ts.call_tool("t", {"path": "b.txt"}, ctx, None)

    assert isinstance(res, ToolReturn)
    assert res.metadata.get("error") is True
    assert "[SYSTEM NOTE]" in res.return_value

    # Second call for the same tool_call_id: nothing left to consume.
    with patch(
        "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
    ) as mock_super:
        mock_super.return_value = "ok"
        res2 = await wrapped_ts.call_tool("t", {"path": "b.txt"}, ctx, None)

    assert res2.return_value == "ok"


@pytest.mark.asyncio
async def test_call_tool_passes_claude_tool_identity_fields():
    """Pre/PostToolUse fire with Claude-standard tool_name/tool_input (and
    tool_response on Post) so tool-name matchers and stdin reads work."""
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    execute = _route_hooks({})
    with (
        patch("zrb.llm.hook.manager.hook_manager.execute_hooks", execute),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
        ) as mock_super,
    ):
        mock_super.return_value = "ok"
        await wrapped_ts.call_tool("Bash", {"command": "ls"}, None, None)

    pre = next(c for c in execute.call_args_list if c.args[0] == HookEvent.PRE_TOOL_USE)
    assert pre.kwargs["tool_name"] == "Bash"
    assert pre.kwargs["tool_input"] == {"command": "ls"}

    post = next(
        c for c in execute.call_args_list if c.args[0] == HookEvent.POST_TOOL_USE
    )
    assert post.kwargs["tool_name"] == "Bash"
    assert post.kwargs["tool_input"] == {"command": "ls"}
    # A plain-string tool result is wrapped under "content" for a JSON-safe payload.
    assert post.kwargs["tool_response"] == {"content": "ok"}


@pytest.mark.asyncio
async def test_posttooluse_failure_passes_claude_tool_identity_fields():
    """PostToolUseFailure carries tool_name/tool_input too."""
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
        await wrapped_ts.call_tool("Bash", {"command": "ls"}, None, None)

    fail = next(
        c
        for c in execute.call_args_list
        if c.args[0] == HookEvent.POST_TOOL_USE_FAILURE
    )
    assert fail.kwargs["tool_name"] == "Bash"
    assert fail.kwargs["tool_input"] == {"command": "ls"}


def testcreate_safe_wrapper_preserves_function_name():
    """Test create_safe_wrapper preserves function name."""

    def my_func():
        pass

    wrapped = create_safe_wrapper(my_func)
    assert wrapped.__name__ == "my_func"


def test_create_agent_uses_default_model_when_none():
    """Test create_agent uses CFG.LLM_MODEL when model=None."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()

    with patch(
        "zrb.llm.agent.common.resolve_configured_model",
        return_value="default-model",
    ) as mock_resolve:
        with patch("pydantic_ai.Agent", mock_agent_class):
            try:
                create_agent(model=None, system_prompt="test", yolo=True)
            except Exception:
                pass  # May fail due to mocking

    # None falls back to CFG.LLM_MODEL before resolution.
    mock_resolve.assert_called_once_with(CFG.LLM_MODEL)


def test_create_agent_resolves_model_once_by_default():
    """With the default resolve_model=True, create_agent resolves the model
    (via resolve_configured_model) exactly once."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    with patch(
        "zrb.llm.agent.common.resolve_configured_model",
        return_value="resolved-model",
    ) as mock_resolve:
        with patch("pydantic_ai.Agent", MagicMock()):
            create_agent(model="base-model", system_prompt="test", yolo=True)

    mock_resolve.assert_called_once_with("base-model")


def test_create_agent_skips_resolution_when_resolve_model_false():
    """Resolve_model=False means the caller already resolved the model, so
    create_agent must NOT resolve it again (which would double-fire
    model_getter/model_renderer, potentially feeding a Model object into a
    getter that expects a tier string)."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    with patch(
        "zrb.llm.agent.common.resolve_configured_model"
    ) as mock_resolve:
        with patch("pydantic_ai.Agent", MagicMock()) as mock_agent_class:
            create_agent(
                model="already-resolved",
                system_prompt="test",
                yolo=True,
                resolve_model=False,
            )

    mock_resolve.assert_not_called()
    # The pre-resolved model is passed straight through to the Agent.
    assert mock_agent_class.call_args.kwargs["model"] == "already-resolved"


def test_create_agent_with_callable_yolo():
    """Test create_agent with callable yolo."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    yolo_func = lambda ctx, tool, args: True  # Always approve

    with patch("pydantic_ai.Agent", mock_agent_class):
        try:
            create_agent(
                model="test-model",
                system_prompt="test",
                yolo=yolo_func,
            )
        except Exception:
            pass  # May fail due to mocking


def test_create_agent_retries_fallback():
    """Test create_agent correctly falls back to CFG.LLM_TOOL_MAX_RETRIES when retries is None."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    mock_config = MagicMock()
    mock_config.model = "default-model"

    with patch("zrb.llm.agent.common.CFG") as mock_cfg:
        mock_cfg.LLM_TOOL_MAX_RETRIES = 5
        # Stubbing the whole singleton means every field create_agent reads has
        # to be a real value, not a MagicMock — the request deadline is compared
        # numerically.
        mock_cfg.LLM_REQUEST_TIMEOUT = 300000
        with patch("pydantic_ai.Agent", mock_agent_class):

            # 1. retries=None (should use CFG.LLM_TOOL_MAX_RETRIES)
            create_agent(model="test-model", retries=None, yolo=True)
            args, kwargs = mock_agent_class.call_args
            assert kwargs.get("retries") == {"tools": 5}

            # 2. retries is specified (should override CFG)
            create_agent(model="test-model", retries=2, yolo=True)
            args, kwargs = mock_agent_class.call_args
            assert kwargs.get("retries") == {"tools": 2}


def _settings_of(mock_agent_class) -> dict:
    _, kwargs = mock_agent_class.call_args
    return kwargs.get("model_settings")


def _default_timeout() -> float:
    """The request deadline every agent carries, in seconds."""
    return CFG.LLM_REQUEST_TIMEOUT / 1000


def _reasoning_defaults() -> dict:
    """The reasoning/caching defaults every agent carries unless overridden."""
    return {
        "openai_reasoning_summary": "auto",
        "openai_prompt_cache_retention": "24h",
        "anthropic_cache": "5m",
    }


def test_create_agent_forces_sequential_for_parallel_unsupported_model():
    """Models in the capabilities deny-list get ``parallel_tool_calls=False``."""
    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="ollama:minimax-m2.7:cloud",
            system_prompt="test",
            yolo=True,
        )

    assert _settings_of(mock_agent_class) == {
        "parallel_tool_calls": False,
        "timeout": _default_timeout(),
        **_reasoning_defaults(),
    }


def test_create_agent_respects_caller_parallel_tool_calls_override():
    """Caller-supplied ``parallel_tool_calls`` is never overwritten."""
    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="ollama:minimax-m2.7:cloud",
            system_prompt="test",
            model_settings={"parallel_tool_calls": True, "temperature": 0.5},
            yolo=True,
        )

    assert _settings_of(mock_agent_class) == {
        "parallel_tool_calls": True,
        "temperature": 0.5,
        "timeout": _default_timeout(),
        **_reasoning_defaults(),
    }


def test_create_agent_leaves_unknown_models_unchanged():
    """A model with no capability entry gets no *capability* injection.

    The request deadline is not a capability constraint — it applies to every
    model — so it is present here while ``parallel_tool_calls`` is not.
    """
    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(model="openai:gpt-4o", system_prompt="test", yolo=True)

    settings = _settings_of(mock_agent_class)
    assert "parallel_tool_calls" not in settings
    assert settings == {"timeout": _default_timeout(), **_reasoning_defaults()}


# ── Request deadline ─────────────────────────────────────────────────────
# A provider that accepts the connection and then stops sending used to block
# the run forever: pydantic-ai waits on the stream and the retry loop only fires
# on a raised exception, so a stall was indistinguishable from thinking. Two
# benchmark cells burned a full 600s wall clock having written no file and
# produced no output.


def test_create_agent_applies_the_configured_request_timeout(monkeypatch):
    from zrb.llm.agent.common import create_agent

    monkeypatch.setattr(CFG, "DEFAULT_LLM_REQUEST_TIMEOUT", "45000")
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_REQUEST_TIMEOUT", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(model="openai:gpt-4o", system_prompt="test", yolo=True)

    assert _settings_of(mock_agent_class) == {"timeout": 45.0, **_reasoning_defaults()}


def test_create_agent_lets_the_caller_own_the_timeout():
    """An explicit ``timeout`` is never overwritten by the configured default."""
    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="openai:gpt-4o",
            system_prompt="test",
            model_settings={"timeout": 5.0},
            yolo=True,
        )

    assert _settings_of(mock_agent_class) == {"timeout": 5.0, **_reasoning_defaults()}


def test_create_agent_lets_the_caller_own_reasoning_defaults():
    """Caller-supplied openai_reasoning_summary/prompt_cache_retention win."""
    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="openai:gpt-4o",
            system_prompt="test",
            model_settings={"openai_reasoning_summary": "detailed"},
            yolo=True,
        )

    settings = _settings_of(mock_agent_class)
    assert settings["openai_reasoning_summary"] == "detailed"
    assert settings["openai_prompt_cache_retention"] == "24h"


def test_create_agent_lets_the_caller_own_anthropic_cache():
    """Caller-supplied anthropic_cache wins over the "5m" default."""
    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="anthropic:claude-sonnet-4-5",
            system_prompt="test",
            model_settings={"anthropic_cache": "1h"},
            yolo=True,
        )

    settings = _settings_of(mock_agent_class)
    assert settings["anthropic_cache"] == "1h"
    assert settings["openai_reasoning_summary"] == "auto"


def test_create_agent_applies_configured_thinking_level(monkeypatch):
    """CFG.LLM_THINKING maps onto pydantic-ai's unified `thinking` setting."""
    from zrb.llm.agent.common import create_agent

    monkeypatch.setattr(CFG, "DEFAULT_LLM_THINKING", "high")
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(model="openai:gpt-4o", system_prompt="test", yolo=True)

    assert _settings_of(mock_agent_class)["thinking"] == "high"


def test_create_agent_omits_thinking_when_unset(monkeypatch):
    """LLM_THINKING unset (the default) leaves `thinking` out entirely, so
    each provider's own default behavior applies untouched."""
    from zrb.llm.agent.common import create_agent

    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(model="openai:gpt-4o", system_prompt="test", yolo=True)

    assert "thinking" not in _settings_of(mock_agent_class)


def test_create_agent_defaults_thinking_true_for_gemini_2_5_and_3(monkeypatch):
    """Gemini 2.5/3 bill `thoughts_tokens` unconditionally but only return a
    readable summary when `thinking` is set — default it on for just this
    model family so the summary is visible without a manual LLM_THINKING."""
    from zrb.llm.agent.common import create_agent

    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="google-gla:gemini-2.5-flash", system_prompt="test", yolo=True
        )

    assert _settings_of(mock_agent_class)["thinking"] is True


def test_create_agent_omits_thinking_default_for_non_thinking_gemini(monkeypatch):
    """Gemini 2.0 and earlier don't get the `thinking=True` nudge — they
    aren't in the `supports_thinking_summary` capability list."""
    from zrb.llm.agent.common import create_agent

    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="google-gla:gemini-2.0-flash", system_prompt="test", yolo=True
        )

    assert "thinking" not in _settings_of(mock_agent_class)


def test_create_agent_configured_thinking_level_wins_over_gemini_default(
    monkeypatch,
):
    """An explicit LLM_THINKING level always wins over the Gemini `True` default."""
    from zrb.llm.agent.common import create_agent

    monkeypatch.setattr(CFG, "DEFAULT_LLM_THINKING", "high")
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="google-gla:gemini-2.5-flash", system_prompt="test", yolo=True
        )

    assert _settings_of(mock_agent_class)["thinking"] == "high"


def test_create_agent_lets_the_caller_own_thinking_for_gemini(monkeypatch):
    """Caller-supplied `thinking` wins over the Gemini `True` default."""
    from zrb.llm.agent.common import create_agent

    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="google-gla:gemini-2.5-flash",
            system_prompt="test",
            model_settings={"thinking": False},
            yolo=True,
        )

    assert _settings_of(mock_agent_class)["thinking"] is False


def test_create_agent_omits_the_timeout_when_disabled(monkeypatch):
    """A non-positive timeout means "no deadline", not "expire immediately"."""
    from zrb.llm.agent.common import create_agent

    monkeypatch.setattr(CFG, "DEFAULT_LLM_REQUEST_TIMEOUT", "0")
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_REQUEST_TIMEOUT", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(model="openai:gpt-4o", system_prompt="test", yolo=True)

    # No timeout key, but the reasoning/caching defaults still apply — those
    # are unconditional, unlike the timeout which can be disabled.
    assert _settings_of(mock_agent_class) == _reasoning_defaults()
