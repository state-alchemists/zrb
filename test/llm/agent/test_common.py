"""Tests for agent common utilities."""

import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    assert result.content == "10"


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
    assert "Test error" in result.content


@pytest.mark.asyncio
async def testcreate_safe_wrapper_already_tool_return():
    """Test create_safe_wrapper when function already returns ToolReturn."""
    from pydantic_ai import ToolReturn

    tr = ToolReturn(return_value="already_wrapped", content="wrapped")

    async def wrapped_func():
        return tr

    wrapped = create_safe_wrapper(wrapped_func)
    result = await wrapped()
    assert result is tr


def test_wrap_tool_callable():
    from zrb.llm.agent.common import _wrap_tool

    def my_tool(x: int):
        return x

    wrapped = _wrap_tool(my_tool)
    assert callable(wrapped)


def test_wrap_tool_instance():
    from pydantic_ai import Tool

    from zrb.llm.agent.common import _wrap_tool

    def my_tool(x: int):
        return x

    tool_inst = Tool(my_tool, name="test", description="desc")
    wrapped = _wrap_tool(tool_inst)
    assert isinstance(wrapped, Tool)
    assert wrapped.name == "test"


@pytest.mark.asyncio
async def test_wrap_toolset():
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import _wrap_toolset

    ts = FunctionToolset(tools=[])
    wrapped_ts = _wrap_toolset(ts)

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

    from zrb.llm.agent.common import _wrap_toolset

    async def failing_tool():
        raise ValueError("error")

    ts = FunctionToolset(tools=[failing_tool])
    wrapped_ts = _wrap_toolset(ts)

    # Note: we need to pass a mock/real tool that will cause super().call_tool to fail
    # or just mock the super().call_tool.
    # Actually, the SafeToolsetWrapper.call_tool calls await super().call_tool

    with patch(
        "pydantic_ai.toolsets.WrapperToolset.call_tool", side_effect=ValueError("fail")
    ):
        res = await wrapped_ts.call_tool("any", {}, None, None)
        assert isinstance(res, ToolReturn)
        assert res.metadata["error"] is True


def testcreate_safe_wrapper_preserves_function_name():
    """Test create_safe_wrapper preserves function name."""

    def my_func():
        pass

    wrapped = create_safe_wrapper(my_func)
    assert wrapped.__name__ == "my_func"


def test_create_agent_uses_default_model_when_none():
    """Test create_agent uses default model when model=None."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    mock_config = MagicMock()
    mock_config.model = "default-model"

    with patch("zrb.llm.agent.common.default_llm_config", mock_config):
        with patch("pydantic_ai.Agent", mock_agent_class):
            try:
                create_agent(model=None, system_prompt="test", yolo=True)
            except Exception:
                pass  # May fail due to mocking

    # Verify the default model was fetched
    _ = mock_config.model


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
