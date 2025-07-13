import asyncio
from datetime import datetime
from unittest import mock

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.task.scheduler import Scheduler


@pytest.mark.asyncio
@mock.patch("zrb.task.scheduler.match_cron", return_value=True)
async def test_scheduler_triggers_on_match(mock_match_cron):
    scheduler = Scheduler(name="test_scheduler", schedule="* * * * *")
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_scheduler",
        color=1,
        icon="⏰",
    )
    with mock.patch.object(ctx, "print") as mock_print:
        with mock.patch.object(scheduler, "get_exchange_xcom") as mock_get_xcom:
            mock_xcom = mock.MagicMock()
            mock_get_xcom.return_value = mock_xcom

            async def run_scheduler():
                await scheduler._exec_action(ctx)

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(run_scheduler(), timeout=0.1)

            mock_match_cron.assert_called_once()
            mock_xcom.push.assert_called_once()


@pytest.mark.asyncio
@mock.patch("zrb.task.scheduler.match_cron", return_value=False)
async def test_scheduler_does_not_trigger_on_no_match(mock_match_cron):
    scheduler = Scheduler(name="test_scheduler", schedule="* * * * *")
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_scheduler",
        color=1,
        icon="⏰",
    )
    with mock.patch.object(ctx, "print") as mock_print:
        with mock.patch.object(scheduler, "get_exchange_xcom") as mock_get_xcom:
            mock_xcom = mock.MagicMock()
            mock_get_xcom.return_value = mock_xcom

            async def run_scheduler():
                await scheduler._exec_action(ctx)

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(run_scheduler(), timeout=0.1)

            mock_match_cron.assert_called_once()
            mock_xcom.push.assert_not_called()
