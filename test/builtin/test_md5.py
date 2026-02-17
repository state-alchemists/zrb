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
async def test_sum_md5_success(tmp_path):
    """Test sum_md5 correctly calculates the checksum of file content."""
    file_path = tmp_path / "test_file.txt"
    file_path.write_bytes(b"file content")

    task = md5_module.sum_md5
    session = get_fresh_session()
    session.set_main_task(task)
    await task.async_run(session=session, kwargs={"file": str(file_path)})
    expected_hash = "d10b4c3ff123b26dc068d43a8bef2d23"
    assert session.final_result == expected_hash


@pytest.mark.asyncio
async def test_sum_md5_file_not_found(tmp_path):
    """Test sum_md5 handles FileNotFoundError."""
    file_path = tmp_path / "nonexistent_file.txt"

    task = md5_module.sum_md5
    session = get_fresh_session()
    session.set_main_task(task)
    with pytest.raises(FileNotFoundError, match="File not found"):
        await task.async_run(session=session, kwargs={"file": str(file_path)})
