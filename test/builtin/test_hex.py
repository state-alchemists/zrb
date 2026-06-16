from unittest import mock

import pytest

from zrb.builtin.hex import decode_hex, dump_hex, encode_hex
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


@pytest.mark.asyncio
async def test_encode_hex():
    res = await encode_hex.async_run(session=get_session(), kwargs={"text": "hi"})
    assert res == "6869"


@pytest.mark.asyncio
async def test_decode_hex():
    res = await decode_hex.async_run(session=get_session(), kwargs={"hex": "6869"})
    assert res == "hi"


@pytest.mark.asyncio
async def test_decode_hex_tolerates_spaces_and_prefix():
    res = await decode_hex.async_run(session=get_session(), kwargs={"hex": "0x68 69"})
    assert res == "hi"


@pytest.mark.asyncio
async def test_decode_hex_invalid_raises_clear_error():
    with pytest.raises(ValueError, match="Invalid hex string"):
        await decode_hex.async_run(session=get_session(), kwargs={"hex": "zz"})


@pytest.mark.asyncio
async def test_dump_hex():
    res = await dump_hex.async_run(session=get_session(), kwargs={"text": "hi"})
    assert "00000000" in res
    assert "68 69" in res
    assert res.rstrip().endswith("hi")
