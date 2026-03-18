from unittest import mock

import pytest

from zrb.builtin import base64 as base64_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


@pytest.fixture
def mock_print():
    return mock.MagicMock()


@pytest.fixture
def session(mock_print):
    return Session(
        shared_ctx=SharedContext(print_fn=mock_print), state_logger=mock.MagicMock()
    )


@pytest.mark.asyncio
async def test_encode_base64(session):
    result = await base64_module.encode_base64.async_run(
        session=session, kwargs={"text": "hello world"}
    )
    assert result == "aGVsbG8gd29ybGQ="


@pytest.mark.asyncio
async def test_decode_base64(session):
    result = await base64_module.decode_base64.async_run(
        session=session, kwargs={"text": "aGVsbG8gd29ybGQ="}
    )
    assert result == "hello world"


@pytest.mark.asyncio
async def test_validate_base64():
    task = base64_module.validate_base64
    # Valid
    s1 = Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())
    await task.async_run(session=s1, kwargs={"text": "aGVsbG8="})
    assert s1.final_result is True
    # Invalid
    s2 = Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())
    await task.async_run(session=s2, kwargs={"text": "invalid!!!"})
    assert s2.final_result is False
