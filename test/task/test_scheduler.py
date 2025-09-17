import asyncio
from unittest import mock
from unittest.mock import MagicMock

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.task.scheduler import Scheduler


@pytest.mark.asyncio
@mock.patch("zrb.task.scheduler.match_cron", return_value=True)
async def test_scheduler_triggers_on_match(mock_match_cron):
    scheduler = Scheduler(name="test_scheduler", schedule="* * * * *")
    shared_ctx = SharedContext(env={})
    # Using MagicMock to simulate session behavior
    mock_session = MagicMock()
    mock_session.task_names = ["test_scheduler"]
    # Directly assign our mock session
    shared_ctx._session = mock_session
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_scheduler",
        color=1,
        icon="⏰",
    )
    with mock.patch.object(scheduler, "push_exchange_xcom") as mock_push_exchange_xcom:

        async def run_scheduler():
            await scheduler._exec_action(ctx)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(run_scheduler(), timeout=0.1)

        mock_match_cron.assert_called_once()
        mock_push_exchange_xcom.assert_called_once()


@pytest.mark.asyncio
@mock.patch("zrb.task.scheduler.match_cron", return_value=False)
async def test_scheduler_does_not_trigger_on_no_match(mock_match_cron):
    scheduler = Scheduler(name="test_scheduler", schedule="* * * * *")
    shared_ctx = SharedContext(env={})
    # Using MagicMock to simulate session behavior
    mock_session = MagicMock()
    mock_session.task_names = ["test_scheduler"]
    # Directly assign our mock session
    shared_ctx._session = mock_session
    ctx = Context(shared_ctx=shared_ctx, task_name="test_scheduler", color=1, icon="⏰")
    with mock.patch.object(scheduler, "push_exchange_xcom") as mock_push_exchange_xcom:

        async def run_scheduler():
            await scheduler._exec_action(ctx)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(run_scheduler(), timeout=0.1)

        mock_match_cron.assert_called_once()
        mock_push_exchange_xcom.assert_not_called()
