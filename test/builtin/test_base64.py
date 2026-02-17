import base64

import pytest

from zrb.builtin import base64 as base64_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_fresh_session():
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_encode_base64():
    """Test the encode_base64 task."""
    task = base64_module.encode_base64
    session = get_fresh_session()
    session.set_main_task(task)
    await task.async_run(session=session, kwargs={"text": "hello world"})
    expected_result = "aGVsbG8gd29ybGQ="
    assert session.final_result == expected_result


@pytest.mark.asyncio
async def test_decode_base64():
    """Test the decode_base64 task."""
    task = base64_module.decode_base64
    session = get_fresh_session()
    session.set_main_task(task)
    await task.async_run(session=session, kwargs={"text": "aGVsbG8gd29ybGQ="})
    expected_result = "hello world"
    assert session.final_result == expected_result


@pytest.mark.asyncio
async def test_decode_base64_invalid_input():
    """Test the decode_base64 task with invalid input."""
    task = base64_module.decode_base64
    session = get_fresh_session()
    session.set_main_task(task)
    with pytest.raises(base64.binascii.Error):
        await task.async_run(session=session, kwargs={"text": "invalid-base64!"})
