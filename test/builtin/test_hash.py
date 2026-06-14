import hashlib
import hmac
from unittest import mock

import pytest

from zrb.builtin.hash import hash_file, hash_hmac, hash_text
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


@pytest.mark.asyncio
async def test_hash_text_default_sha256():
    res = await hash_text.async_run(
        session=get_session(), kwargs={"text": "hello", "algorithm": "sha256"}
    )
    assert res == hashlib.sha256(b"hello").hexdigest()


@pytest.mark.asyncio
async def test_hash_text_md5():
    res = await hash_text.async_run(
        session=get_session(), kwargs={"text": "hello", "algorithm": "md5"}
    )
    assert res == hashlib.md5(b"hello").hexdigest()


@pytest.mark.asyncio
async def test_hash_file(tmp_path):
    target = tmp_path / "data.bin"
    target.write_bytes(b"hello world")
    res = await hash_file.async_run(
        session=get_session(),
        kwargs={"file": str(target), "algorithm": "sha256"},
    )
    assert res == hashlib.sha256(b"hello world").hexdigest()


@pytest.mark.asyncio
async def test_hash_file_missing_raises_clear_error():
    with pytest.raises(ValueError, match="File not found"):
        await hash_file.async_run(
            session=get_session(),
            kwargs={"file": "/no/such/file.bin", "algorithm": "sha256"},
        )


@pytest.mark.asyncio
async def test_hash_hmac():
    res = await hash_hmac.async_run(
        session=get_session(),
        kwargs={"key": "secret", "text": "message", "algorithm": "sha256"},
    )
    expected = hmac.new(b"secret", b"message", "sha256").hexdigest()
    assert res == expected
