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
