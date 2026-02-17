from unittest import mock

import pytest

from zrb.builtin import md5 as md5_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_fresh_session():
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_hash_md5_success():
    """Test hash_md5 correctly hashes the input text."""
    task = md5_module.hash_md5
    session = get_fresh_session()
    session.set_main_task(task)
    await task.async_run(session=session, kwargs={"text": "hello world"})
    expected_hash = "5eb63bbbe01eeed093cb22bb8f5acdc3"
    assert session.final_result == expected_hash


@pytest.mark.asyncio
@mock.patch("builtins.open", new_callable=mock.mock_open, read_data=b"file content")
async def test_sum_md5_success(mock_open):
    """Test sum_md5 correctly calculates the checksum of file content."""
    task = md5_module.sum_md5
    session = get_fresh_session()
    session.set_main_task(task)
    await task.async_run(session=session, kwargs={"file": "test_file.txt"})
    expected_hash = "d10b4c3ff123b26dc068d43a8bef2d23"
    assert session.final_result == expected_hash
    mock_open.assert_called_once_with("test_file.txt", mode="rb")


@pytest.mark.asyncio
@mock.patch("builtins.open", side_effect=FileNotFoundError("File not found"))
async def test_sum_md5_file_not_found(mock_open):
    """Test sum_md5 handles FileNotFoundError."""
    task = md5_module.sum_md5
    session = get_fresh_session()
    session.set_main_task(task)
    with pytest.raises(FileNotFoundError, match="File not found"):
        await task.async_run(session=session, kwargs={"file": "nonexistent_file.txt"})
    mock_open.assert_called_once_with("nonexistent_file.txt", mode="rb")
