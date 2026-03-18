from unittest import mock
import pytest
from zrb.builtin import md5 as md5_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session

@pytest.fixture
def session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())

@pytest.mark.asyncio
async def test_hash_md5_success(session):
    result = await md5_module.hash_md5.async_run(session=session, kwargs={"text": "hello world"})
    assert result == "5eb63bbbe01eeed093cb22bb8f5acdc3"

@pytest.mark.asyncio
async def test_sum_md5_success(session):
    with mock.patch("builtins.open", mock.mock_open(read_data=b"file content")):
        result = await md5_module.sum_md5.async_run(session=session, kwargs={"file": "test.txt"})
        assert result == "d10b4c3ff123b26dc068d43a8bef2d23"

@pytest.mark.asyncio
async def test_validate_md5():
    task = md5_module.validate_md5
    # Valid
    s1 = Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())
    await task.async_run(session=s1, kwargs={"hash": "d41d8cd98f00b204e9800998ecf8427e"})
    assert s1.final_result is True
    # Invalid
    s2 = Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())
    await task.async_run(session=s2, kwargs={"hash": "invalid"})
    assert s2.final_result is False
