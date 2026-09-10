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


@pytest.mark.asyncio
async def test_parse_cron_unparsable_field_raises_clear_error():
    """Right field count but garbage in a field explains how to fix it."""
    with pytest.raises(ValueError, match="could not parse a field"):
        await parse_cron.async_run(
            session=get_session(), kwargs={"expression": "a b c d e", "count": 1}
        )


@pytest.mark.asyncio
async def test_parse_cron_reports_when_fewer_runs_found(monkeypatch):
    """A pattern with no match inside the scan window says so instead of
    silently printing fewer runs."""
    # Shrink the scan window (module-level constant) so exhausting it is quick.
    import zrb.builtin.cron as cron_module

    monkeypatch.setattr(cron_module, "_MAX_SCAN_MINUTES", 60 * 24 * 30)
    # Feb 30th never exists, so no candidate minute can ever match.
    lines = []
    session = Session(
        shared_ctx=SharedContext(print_fn=lambda *a, **k: lines.append(str(a[0]))),
        state_logger=mock.MagicMock(),
    )
    result = await parse_cron.async_run(
        session=session, kwargs={"expression": "0 0 30 2 *", "count": 3}
    )
    assert result == ""
    assert any("only 0 run(s) found" in line for line in lines)
