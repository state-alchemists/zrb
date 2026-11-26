import asyncio
from unittest import mock

import pytest

from zrb.attr.tpl import Tpl
from zrb.context.any_context import AnyContext
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.scheduler import Scheduler


@pytest.fixture
def mock_session():
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
@mock.patch("zrb.task.scheduler.match_cron", return_value=True)
async def test_scheduler_triggers_on_match(mock_match_cron, mock_session):
    import datetime

    scheduler = Scheduler(name="test_scheduler", schedule="* * * * *")
    mock_session.register_task(scheduler)

    with mock.patch.object(scheduler, "push_exchange_xcom") as mock_push_exchange_xcom:
        with mock.patch("zrb.task.scheduler.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = datetime.datetime(
                2026, 1, 1, 10, 0, 30
            )

            scheduler_task = asyncio.create_task(scheduler.exec(mock_session))

            await asyncio.sleep(0.01)

            scheduler_task.cancel()

            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass

            await asyncio.sleep(0.01)

            mock_match_cron.assert_called_once()
            mock_push_exchange_xcom.assert_called_once()


@pytest.mark.asyncio
@mock.patch("zrb.task.scheduler.match_cron", return_value=False)
async def test_scheduler_does_not_trigger_on_no_match(mock_match_cron, mock_session):
    import datetime

    scheduler = Scheduler(name="test_scheduler", schedule="* * * * *")
    mock_session.register_task(scheduler)

    with mock.patch.object(scheduler, "push_exchange_xcom") as mock_push_exchange_xcom:
        # Pin the clock, as `test_scheduler_triggers_on_match` does: the loop
        # sleeps to the next minute boundary, so on a real clock this window can
        # straddle one and sample two minutes — two `match_cron` calls, which is
        # correct for `* * * * *` and makes the count assertion flake.
        with mock.patch("zrb.task.scheduler.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = datetime.datetime(
                2026, 1, 1, 10, 0, 30
            )

            scheduler_task = asyncio.create_task(scheduler.exec(mock_session))

            await asyncio.sleep(0.01)

            scheduler_task.cancel()

            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass

            await asyncio.sleep(0.01)

            mock_match_cron.assert_called_once()
            mock_push_exchange_xcom.assert_not_called()


@pytest.mark.asyncio
@mock.patch("zrb.task.scheduler.match_cron", return_value=True)
async def test_scheduler_fires_once_per_minute_with_subminute_tick(
    mock_match_cron, mock_session
):
    """A sub-minute tick must not fire several times inside one matching minute."""
    import datetime

    scheduler = Scheduler(name="test_scheduler", schedule="* * * * *")
    mock_session.register_task(scheduler)

    fixed_now = datetime.datetime(2026, 1, 1, 10, 0, 30)

    with mock.patch.object(scheduler, "push_exchange_xcom") as mock_push:
        with mock.patch("zrb.task.scheduler.CFG") as mock_cfg:
            mock_cfg.SCHEDULER_TICK_INTERVAL = 1  # 1ms tick
            with mock.patch("zrb.task.scheduler.datetime") as mock_datetime:
                mock_datetime.datetime.now.return_value = fixed_now

                scheduler_task = asyncio.create_task(scheduler.exec(mock_session))
                await asyncio.sleep(0.05)  # dozens of 1ms ticks
                scheduler_task.cancel()
                try:
                    await scheduler_task
                except asyncio.CancelledError:
                    pass

                assert mock_datetime.datetime.now.call_count > 1

        mock_push.assert_called_once()


def test_scheduler_rejects_an_unknown_cron_shortcut():
    """`@dialy` matches nothing forever, so it is refused, not monitored."""
    with pytest.raises(ValueError, match="Unknown cron shortcut '@dialy'"):
        Scheduler(name="test_scheduler", schedule="@dialy")


def test_scheduler_rejects_an_unparsable_cron_field():
    with pytest.raises(ValueError, match="could not parse a field"):
        Scheduler(name="test_scheduler", schedule="a b c d e")


@pytest.mark.parametrize("schedule", [None, "@minutely", "@daily", "*/5 * * * *"])
def test_scheduler_accepts_a_usable_schedule(schedule):
    assert Scheduler(name="test_scheduler", schedule=schedule).name == "test_scheduler"


@pytest.mark.asyncio
async def test_scheduler_rejects_an_unknown_shortcut_rendered_at_run_time():
    """A `Tpl` schedule's text arrives late, so it is checked before the loop."""
    scheduler = Scheduler(name="test_scheduler", schedule=Tpl("@dialy"))
    ctx = mock.MagicMock(spec=AnyContext)
    ctx.render = mock.MagicMock(return_value="@dialy")

    with pytest.raises(ValueError, match="Unknown cron shortcut '@dialy'"):
        await scheduler.exec_action(ctx)
