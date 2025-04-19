from types import SimpleNamespace  # Keep for fixture
from unittest import mock

import pytest

# Import the task objects themselves, not the original functions
from zrb.builtin import base64 as base64_module


@pytest.fixture
def mock_context():
    """Fixture for a mocked AnyContext."""
    context = mock.Mock()
    # Use SimpleNamespace for attribute assignment if needed, otherwise remove import
    context.input = SimpleNamespace()
    context.print = mock.Mock()
    context.log_error = mock.Mock()
    return context


@pytest.mark.asyncio
async def test_encode_base64(mock_context):  # Use fixture, mark async
    """Test the encode_base64 task."""
    # Setup mock context and input
    mock_context.input.text = "hello world"

    # Get the task object
    encode_task = base64_module.encode_base64

    # Execute the task's action
    result = await encode_task._exec_action(mock_context)

    # Assertions
    expected_result = "aGVsbG8gd29ybGQ="
    assert result == expected_result
    mock_context.print.assert_called_once_with(expected_result)


@pytest.mark.asyncio
async def test_decode_base64(mock_context):  # Use fixture
    """Test the decode_base64 task."""
    # Setup mock context and input
    mock_context.input.text = "aGVsbG8gd29ybGQ="

    # Get the task object
    decode_task = base64_module.decode_base64

    # Execute the task's action
    result = await decode_task._exec_action(mock_context)

    # Assertions
    expected_result = "hello world"
    assert result == expected_result
    mock_context.print.assert_called_once_with(expected_result)


@pytest.mark.asyncio
async def test_decode_base64_invalid_input(mock_context):  # Use fixture
    """Test the decode_base64 task with invalid input."""
    import base64

    # Setup mock context and input
    mock_context.input.text = "invalid-base64!"

    # Get the task object
    decode_task = base64_module.decode_base64

    # Execute the task's action and expect an error
    with pytest.raises(base64.binascii.Error):
        await decode_task._exec_action(mock_context)

    # Assertions
    mock_context.print.assert_not_called()
