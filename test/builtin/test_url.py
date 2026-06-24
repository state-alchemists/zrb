import json
from unittest import mock

import pytest

from zrb.builtin.url import decode_url, encode_url, parse_url
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


@pytest.mark.asyncio
async def test_encode_url():
    res = await encode_url.async_run(session=get_session(), kwargs={"text": "a b&c=d"})
    assert res == "a%20b%26c%3Dd"


@pytest.mark.asyncio
async def test_decode_url():
    res = await decode_url.async_run(
        session=get_session(), kwargs={"text": "a%20b%26c%3Dd"}
    )
    assert res == "a b&c=d"


@pytest.mark.asyncio
async def test_parse_url():
    res = await parse_url.async_run(
        session=get_session(),
        kwargs={"url": "https://user:pw@example.com:8443/path?a=1&b=2#frag"},
    )
    parsed = json.loads(res)
    assert parsed["scheme"] == "https"
    assert parsed["hostname"] == "example.com"
    assert parsed["port"] == 8443
    assert parsed["path"] == "/path"
    assert parsed["query"] == {"a": "1", "b": "2"}
    assert parsed["fragment"] == "frag"
