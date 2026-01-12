import inspect
from unittest.mock import MagicMock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.task.llm.tool_wrapper import (
    ToolExecutionCancelled,
    ToolExecutionError,
    _has_context_parameter,
    _is_annotated_with_context,
    wrap_tool,
)


# Create a dummy context class for testing annotation checks
class RunContext:
    pass


@pytest.fixture
def mock_context():
    return MagicMock(spec=AnyContext)


def test_has_context_parameter():
    def func_no_ctx(a: int):
        pass

    sig = inspect.signature(func_no_ctx)
    assert not _has_context_parameter(sig, AnyContext)

    def func_with_ctx(ctx: AnyContext):
        pass

    sig = inspect.signature(func_with_ctx)
    assert _has_context_parameter(sig, AnyContext)

    def func_with_optional_ctx(ctx: AnyContext | None):
        pass

    sig = inspect.signature(func_with_optional_ctx)
    assert _has_context_parameter(sig, AnyContext)


def test_is_annotated_with_context():
    assert _is_annotated_with_context(AnyContext, AnyContext)
    assert not _is_annotated_with_context(int, AnyContext)
    assert _is_annotated_with_context(AnyContext | None, AnyContext)


@pytest.mark.asyncio
async def test_wrap_tool_execution_success(mock_context):
    async def my_tool(ctx: AnyContext, x: int) -> int:
        return x * 2

    # Mock pydantic_ai.Tool
    with patch("pydantic_ai.Tool") as MockTool:
        wrapped_tool = wrap_tool(my_tool, mock_context, yolo_mode=True)

        # The wrapped function is passed to Tool constructor.
        # We want to call the wrapped function.
        wrapper_func = MockTool.call_args[0][0]

        # The wrapper signature should NOT include ctx because it is injected
        sig = inspect.signature(wrapper_func)
        assert "ctx" not in sig.parameters

        # Execute wrapper
        # args/kwargs passed by LLM (so no ctx)
        result = await wrapper_func(x=21)
        assert result == 42


@pytest.mark.asyncio
async def test_wrap_tool_execution_error(mock_context):
    async def my_failing_tool(ctx: AnyContext):
        raise ValueError("Boom")

    with patch("pydantic_ai.Tool") as MockTool:
        wrapped_tool = wrap_tool(my_failing_tool, mock_context, yolo_mode=True)
        wrapper_func = MockTool.call_args[0][0]

        # Execute wrapper, should catch exception and return JSON error
        result = await wrapper_func()
        # The JSON output structure: {"tool_name": ..., "error_type": "ValueError", ...}
        assert "ValueError" in result
        assert "Boom" in result


@pytest.mark.asyncio
async def test_wrap_tool_rate_limit_error(mock_context):
    async def my_big_tool(ctx: AnyContext):
        return "huge result"

    with patch("pydantic_ai.Tool") as MockTool:
        with patch("zrb.task.llm.tool_wrapper.llm_rate_limitter") as mock_limiter:
            mock_limiter.count_token.return_value = 1000
            mock_limiter.max_tokens_per_tool_call_result = 10

            wrapped_tool = wrap_tool(my_big_tool, mock_context, yolo_mode=True)
            wrapper_func = MockTool.call_args[0][0]

            result = await wrapper_func()
            assert "ValueError" in result
            assert "too large" in result


@pytest.mark.asyncio
async def test_wrap_tool_interactive_approval(mock_context):
    # Simulate TTY and interactive mode
    mock_context.is_web_mode = False
    mock_context.is_tty = True

    async def dangerous_tool(ctx: AnyContext):
        return "done"

    with patch("pydantic_ai.Tool") as MockTool:
        
        async def mock_read_line(args, kwargs):
            # This will be controlled by side_effect
            return mock_read_line.return_value
        
        mock_read_line.return_value = "yes"
        
        with patch(
            "zrb.task.llm.tool_wrapper._read_line", side_effect=mock_read_line
        ) as mock_read_patch:
            # First call: approve
            mock_read_line.return_value = "yes"

            # yolo_mode=False enables confirmation
            wrap_tool(dangerous_tool, mock_context, yolo_mode=False)
            wrapper_func = MockTool.call_args[0][0]

            result = await wrapper_func()
            assert result == "done"

            # Second call: reject
            mock_read_line.return_value = "no"
            result = await wrapper_func()
            assert "ToolExecutionCancelled" in result
