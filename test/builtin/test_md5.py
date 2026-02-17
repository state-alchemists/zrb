from types import SimpleNamespace
from unittest import mock

import pytest

# Import task objects from the module
from zrb.builtin import md5 as md5_module


@pytest.fixture
def mock_context():
    """Fixture for a mocked AnyContext."""
    context = mock.MagicMock()
    context.input = SimpleNamespace()
    context.print = mock.MagicMock()
    context.log_error = mock.MagicMock()  # Keep for consistency, might be needed later
    return context


# --- Tests for hash_md5 ---


from zrb.session.session import Session
from zrb.context.shared_context import SharedContext

@pytest.fixture
def mock_print():
    return mock.MagicMock()

@pytest.fixture
def session(mock_print):
    shared_ctx = SharedContext(print_fn=mock_print)
    return Session(shared_ctx=shared_ctx, state_logger=mock.MagicMock())

@pytest.mark.asyncio
async def test_hash_md5_success(session, mock_print):
    """Test hash_md5 correctly hashes the input text."""
    input_text = "hello world"
    expected_hash = "5eb63bbbe01eeed093cb22bb8f5acdc3"

    # Get the task object
    hash_task = md5_module.hash_md5

    # Execute publicly
    result = await hash_task.async_run(session=session, kwargs={"text": input_text})

    assert result == expected_hash
    # Check if the hash was printed (ignoring styling)
    printed_text = "".join(call.args[0] for call in mock_print.call_args_list)
    assert expected_hash in printed_text


# --- Tests for sum_md5 ---


@pytest.mark.asyncio
async def test_sum_md5_success(session, mock_print):
    """Test sum_md5 correctly calculates the checksum of file content."""
    file_path = "test_file.txt"
    expected_hash = "d10b4c3ff123b26dc068d43a8bef2d23"  # Correct MD5 of b"file content"
    
    # Get the task object
    sum_task = md5_module.sum_md5

    with mock.patch("builtins.open", mock.mock_open(read_data=b"file content")) as mock_open:
        # Execute publicly
        result = await sum_task.async_run(session=session, kwargs={"file": file_path})

        mock_open.assert_called_once_with(file_path, mode="rb")
        assert result == expected_hash
        # Check if the hash was printed (ignoring styling)
        printed_text = "".join(call.args[0] for call in mock_print.call_args_list)
        assert expected_hash in printed_text


@pytest.mark.asyncio
async def test_sum_md5_file_not_found(session, mock_print):
    """Test sum_md5 handles FileNotFoundError."""
    file_path = "nonexistent_file.txt"

    # Get the task object
    sum_task = md5_module.sum_md5

    with mock.patch("builtins.open", side_effect=FileNotFoundError("File not found")) as mock_open:
        # Execute publicly
        with pytest.raises(FileNotFoundError, match="File not found"):
            await sum_task.async_run(session=session, kwargs={"file": file_path})

        # Verify open was called at least once with the correct parameters
        mock_open.assert_any_call(file_path, mode="rb")
