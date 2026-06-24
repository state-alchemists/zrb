import datetime
from unittest import mock

import pytest

from zrb.builtin.cron import parse_cron
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


@pytest.mark.asyncio
async def test_parse_cron_next_runs():
    res = await parse_cron.async_run(
        session=get_session(), kwargs={"expression": "*/30 * * * *", "count": 3}
    )
    runs = res.splitlines()
    assert len(runs) == 3
    for run in runs:
        moment = datetime.datetime.fromisoformat(run)
        assert moment.minute in (0, 30)


@pytest.mark.asyncio
async def test_parse_cron_special_pattern():
    res = await parse_cron.async_run(
        session=get_session(), kwargs={"expression": "@hourly", "count": 2}
    )
    runs = res.splitlines()
    assert len(runs) == 2
    for run in runs:
        assert datetime.datetime.fromisoformat(run).minute == 0


@pytest.mark.asyncio
async def test_parse_cron_wrong_field_count_raises_clear_error():
    with pytest.raises(ValueError, match="expected 5 space-separated fields"):
        await parse_cron.async_run(
            session=get_session(),
            kwargs={"expression": "not a cron", "count": 1},
        )


@pytest.mark.asyncio
async def test_parse_cron_unknown_shortcut_raises_clear_error():
    with pytest.raises(ValueError, match="Unknown cron shortcut"):
        await parse_cron.async_run(
            session=get_session(),
            kwargs={"expression": "@nope", "count": 1},
        )
