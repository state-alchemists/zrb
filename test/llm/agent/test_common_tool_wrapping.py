"""Tests for agent common utilities."""

from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.agent.common import create_safe_wrapper, safe_copy_result


def _route_hooks(mapping):
    """An execute_hooks mock that returns per-event HookExecutionResult lists."""

    async def _execute(event, data, *args, **kwargs):
        return mapping.get(event, [])

    return AsyncMock(side_effect=_execute)


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
