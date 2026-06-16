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


@pytest.mark.asyncio
async def test_encode_decode_base64_url_safe(session):
    # Bytes whose standard base64 contains + and / use -, _ in URL-safe mode.
    encoded = await base64_module.encode_base64.async_run(
        session=session, kwargs={"text": "<<???>>", "url_safe": True}
    )
    assert "+" not in encoded and "/" not in encoded
    decoded = await base64_module.decode_base64.async_run(
        session=Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock()),
        kwargs={"text": encoded, "url_safe": True},
    )
    assert decoded == "<<???>>"


@pytest.mark.asyncio
async def test_decode_base64_invalid_raises_clear_error():
    s = Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())
    with pytest.raises(ValueError, match="Invalid base64 input"):
        await base64_module.decode_base64.async_run(
            session=s, kwargs={"text": "!!!notb64"}
        )


@pytest.mark.asyncio
async def test_validate_base64_of_binary():
    # Base64 of non-UTF-8 binary must validate (the old text-only check failed here).
    import base64 as _b64

    blob = _b64.b64encode(bytes([0xFF, 0xFE, 0x00, 0x80])).decode()
    s = Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())
    await base64_module.validate_base64.async_run(session=s, kwargs={"text": blob})
    assert s.final_result is True
