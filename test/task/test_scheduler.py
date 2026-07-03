import asyncio
from unittest import mock

import pytest

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
    # Create a task for the scheduler
    scheduler = Scheduler(name="test_scheduler", schedule="* * * * *")
    mock_session.register_task(scheduler)

    with mock.patch.object(scheduler, "push_exchange_xcom") as mock_push_exchange_xcom:
        # Create a task that will run the scheduler
        scheduler_task = asyncio.create_task(scheduler.exec(mock_session))

        # Wait a bit for the scheduler to run
        await asyncio.sleep(0.01)

        # Cancel the scheduler task
        scheduler_task.cancel()

        # Wait for cancellation to complete
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

        # Give any background tasks time to clean up
        await asyncio.sleep(0.01)

        mock_match_cron.assert_called_once()
        mock_push_exchange_xcom.assert_called_once()


@pytest.mark.asyncio
@mock.patch("zrb.task.scheduler.match_cron", return_value=False)
async def test_scheduler_does_not_trigger_on_no_match(mock_match_cron, mock_session):
    # Create a task for the scheduler
    scheduler = Scheduler(name="test_scheduler", schedule="* * * * *")
    mock_session.register_task(scheduler)

    with mock.patch.object(scheduler, "push_exchange_xcom") as mock_push_exchange_xcom:
        # Create a task that will run the scheduler
        scheduler_task = asyncio.create_task(scheduler.exec(mock_session))

        # Wait a bit for the scheduler to run
        await asyncio.sleep(0.01)

        # Cancel the scheduler task
        scheduler_task.cancel()

        # Wait for cancellation to complete
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

        # Give any background tasks time to clean up
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
                # Pin the clock inside one minute so the test cannot flake
                # across a real minute boundary.
                mock_datetime.datetime.now.return_value = fixed_now

                scheduler_task = asyncio.create_task(scheduler.exec(mock_session))
                await asyncio.sleep(0.05)  # dozens of 1ms ticks
                scheduler_task.cancel()
                try:
                    await scheduler_task
                except asyncio.CancelledError:
                    pass

                # The loop kept sampling the clock...
                assert mock_datetime.datetime.now.call_count > 1

        # ...but the matching minute fired exactly once.
        mock_push.assert_called_once()
