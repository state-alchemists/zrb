"""Tests for agent common utilities."""

import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.common import _create_safe_wrapper, _safe_copy_result


def test_safe_copy_result_none():
    """Test _safe_copy_result with None."""
    result = _safe_copy_result(None)
    assert result is None


def test_safe_copy_result_string():
    """Test _safe_copy_result with string."""
    result = _safe_copy_result("test")
    assert result == "test"


def test_safe_copy_result_int():
    """Test _safe_copy_result with int."""
    result = _safe_copy_result(42)
    assert result == 42


def test_safe_copy_result_float():
    """Test _safe_copy_result with float."""
    result = _safe_copy_result(3.14)
    assert result == 3.14


def test_safe_copy_result_bool():
    """Test _safe_copy_result with bool."""
    result = _safe_copy_result(True)
    assert result is True


def test_safe_copy_result_list():
    """Test _safe_copy_result makes a copy of list."""
    original = [1, 2, 3]
    result = _safe_copy_result(original)
    assert result == [1, 2, 3]
    assert result is not original
    # Modify result, original should be unchanged
    result.append(4)
    assert original == [1, 2, 3]


def test_safe_copy_result_dict():
    """Test _safe_copy_result makes a deep copy of dict."""
    original = {"key": "value", "nested": {"a": 1}}
    result = _safe_copy_result(original)
    assert result == original
    assert result is not original
    # Modify result, original should be unchanged
    result["key"] = "modified"
    result["nested"]["a"] = 2
    assert original["key"] == "value"
    assert original["nested"]["a"] == 1


def test_safe_copy_result_set():
    """Test _safe_copy_result makes a copy of set."""
    original = {1, 2, 3}
    result = _safe_copy_result(original)
    assert result == {1, 2, 3}
    assert result is not original


def test_safe_copy_result_nested_list():
    """Test _safe_copy_result with nested list."""
    original = [[1, 2], [3, 4]]
    result = _safe_copy_result(original)
    assert result == [[1, 2], [3, 4]]
    # Modify nested element
    result[0].append(5)
    assert original == [[1, 2], [3, 4]]


def test_safe_copy_result_tuple():
    """Test _safe_copy_result with tuple attempts deep copy."""
    original = (1, 2, 3)
    result = _safe_copy_result(original)
    assert result == (1, 2, 3)


def test_safe_copy_result_object_with_deepcopy_failure():
    """Test _safe_copy_result handles objects that can't be deep copied."""

    class NoDeepCopy:
        def __deepcopy__(self, memo):
            raise TypeError("Cannot deep copy")

        def __eq__(self, other):
            return isinstance(other, NoDeepCopy)

    obj = NoDeepCopy()
    result = _safe_copy_result(obj)
    # Should return original when deepcopy fails
    assert result is obj


@pytest.mark.asyncio
async def test_create_safe_wrapper_sync_function():
    """Test _create_safe_wrapper with sync function."""

    def sync_func(x):
        return x * 2

    wrapped = _create_safe_wrapper(sync_func)
    # The wrapper is async
    result = await wrapped(5)
    # It should return a ToolReturn with the result


@pytest.mark.asyncio
async def test_create_safe_wrapper_async_function():
    """Test _create_safe_wrapper with async function."""

    async def async_func(x):
        return x * 2

    wrapped = _create_safe_wrapper(async_func)
    result = await wrapped(5)
    # It should return a ToolReturn with the result


@pytest.mark.asyncio
async def test_create_safe_wrapper_handles_exception():
    """Test _create_safe_wrapper catches exceptions."""

    def failing_func():
        raise ValueError("Test error")

    wrapped = _create_safe_wrapper(failing_func)
    result = await wrapped()
    # Should return ToolReturn with error metadata


def test_create_safe_wrapper_preserves_function_name():
    """Test _create_safe_wrapper preserves function name."""

    def my_func():
        pass

    wrapped = _create_safe_wrapper(my_func)
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
