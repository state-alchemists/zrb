from unittest import mock
import pytest
from zrb.builtin import base64 as base64_module
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
async def test_encode_base64(session, mock_print):
    """Test the encode_base64 task."""
    # Get the task object
    encode_task = base64_module.encode_base64

    # Execute publicly
    result = await encode_task.async_run(
        session=session,
        kwargs={"text": "hello world"}
    )

    # Assertions
    expected_result = "aGVsbG8gd29ybGQ="
    assert result == expected_result
    # Check if the result was printed
    printed_text = "".join(call.args[0] for call in mock_print.call_args_list)
    assert expected_result in printed_text


@pytest.mark.asyncio
async def test_decode_base64(session, mock_print):
    """Test the decode_base64 task."""
    # Get the task object
    decode_task = base64_module.decode_base64

    # Execute publicly
    result = await decode_task.async_run(
        session=session,
        kwargs={"text": "aGVsbG8gd29ybGQ="}
    )

    # Assertions
    expected_result = "hello world"
    assert result == expected_result
    # Check if the result was printed
    printed_text = "".join(call.args[0] for call in mock_print.call_args_list)
    assert expected_result in printed_text


@pytest.mark.asyncio
async def test_decode_base64_invalid_input(session, mock_print):
    """Test the decode_base64 task with invalid input."""
    import base64

    # Get the task object
    decode_task = base64_module.decode_base64

    # Execute publicly and expect an error
    with pytest.raises(base64.binascii.Error):
        await decode_task.async_run(
            session=session,
            kwargs={"text": "invalid-base64!"}
        )
