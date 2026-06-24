from unittest import mock

import pytest

from zrb.builtin.datetime import epoch_to_iso, iso_to_epoch, now
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


@pytest.mark.asyncio
async def test_now_returns_epoch():
    res = await now.async_run(session=get_session(), kwargs={"timezone": "utc"})
    assert res.isdigit()


@pytest.mark.asyncio
async def test_epoch_to_iso_utc():
    res = await epoch_to_iso.async_run(
        session=get_session(), kwargs={"epoch": "0", "timezone": "utc"}
    )
    assert res == "1970-01-01T00:00:00+00:00"


@pytest.mark.asyncio
async def test_iso_to_epoch():
    res = await iso_to_epoch.async_run(
        session=get_session(), kwargs={"datetime": "1970-01-01T00:00:00+00:00"}
    )
    assert res == "0"


@pytest.mark.asyncio
async def test_iso_to_epoch_naive_treated_as_utc():
    res = await iso_to_epoch.async_run(
        session=get_session(), kwargs={"datetime": "1970-01-01T00:00:00"}
    )
    assert res == "0"


@pytest.mark.asyncio
async def test_epoch_to_iso_invalid_raises_clear_error():
    with pytest.raises(ValueError, match="Invalid epoch"):
        await epoch_to_iso.async_run(
            session=get_session(), kwargs={"epoch": "abc", "timezone": "utc"}
        )


@pytest.mark.asyncio
async def test_iso_to_epoch_invalid_raises_clear_error():
    with pytest.raises(ValueError, match="Invalid ISO 8601 datetime"):
        await iso_to_epoch.async_run(
            session=get_session(), kwargs={"datetime": "garbage"}
        )


@pytest.mark.asyncio
async def test_round_trip():
    iso = await epoch_to_iso.async_run(
        session=get_session(), kwargs={"epoch": "1750000000", "timezone": "utc"}
    )
    back = await iso_to_epoch.async_run(session=get_session(), kwargs={"datetime": iso})
    assert back == "1750000000"
