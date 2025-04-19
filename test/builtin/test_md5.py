from types import SimpleNamespace
from unittest import mock

import pytest

# Import task objects from the module
from zrb.builtin import md5 as md5_module


@pytest.fixture
def mock_context():
    """Fixture for a mocked AnyContext."""
    context = mock.Mock()
    context.input = SimpleNamespace()
    context.print = mock.Mock()
    context.log_error = mock.Mock()  # Keep for consistency, might be needed later
    return context


# --- Tests for hash_md5 ---


@pytest.mark.asyncio
async def test_hash_md5_success(mock_context):
    """Test hash_md5 correctly hashes the input text."""
    input_text = "hello world"
    expected_hash = "5eb63bbbe01eeed093cb22bb8f5acdc3"
    mock_context.input.text = input_text

    # Get the task object
    hash_task = md5_module.hash_md5

    result = await hash_task._exec_action(mock_context)

    assert result == expected_hash
    mock_context.print.assert_called_once_with(expected_hash)


# --- Tests for sum_md5 ---


@pytest.mark.asyncio
@mock.patch("builtins.open", new_callable=mock.mock_open, read_data=b"file content")
async def test_sum_md5_success(mock_open, mock_context):
    """Test sum_md5 correctly calculates the checksum of file content."""
    file_path = "test_file.txt"
    expected_hash = "d10b4c3ff123b26dc068d43a8bef2d23"  # Correct MD5 of b"file content"
    mock_context.input.file = file_path

    # Get the task object
    sum_task = md5_module.sum_md5

    result = await sum_task._exec_action(mock_context)

    mock_open.assert_called_once_with(file_path, mode="rb")
    assert result == expected_hash
    mock_context.print.assert_called_once_with(expected_hash)


@pytest.mark.asyncio
@mock.patch("builtins.open", side_effect=FileNotFoundError("File not found"))
async def test_sum_md5_file_not_found(mock_open, mock_context):
    """Test sum_md5 handles FileNotFoundError."""
    file_path = "nonexistent_file.txt"
    mock_context.input.file = file_path

    # Get the task object
    sum_task = md5_module.sum_md5

    with pytest.raises(FileNotFoundError, match="File not found"):
        await sum_task._exec_action(mock_context)

    mock_open.assert_called_once_with(file_path, mode="rb")
    mock_context.print.assert_not_called()
