import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.session.any_session import AnySession
from zrb.task.base.monitoring import monitor_task_readiness
from zrb.task.base_task import BaseTask
from zrb.task_status.task_status import TaskStatus
from zrb.xcom.xcom import Xcom


@pytest.mark.asyncio
async def test_monitor_no_readiness_checks():
    task = BaseTask(name="test_task")
    session = MagicMock(spec=AnySession)
    ctx = MagicMock(spec=AnyContext)
    with patch.object(task, "get_ctx", return_value=ctx):

        async def mock_action_coro():
            return None

        action_coro = asyncio.create_task(mock_action_coro())
        # Should return immediately
        await monitor_task_readiness(task, session, action_coro)
        ctx.log_debug.assert_called_with(
            "No readiness checks defined, monitoring is not applicable."
        )


@pytest.mark.asyncio
async def test_monitor_readiness_pass_loop():
    # Setup task with readiness check
    check_task = BaseTask(name="check_task")

    async def mock_exec_chain(*args, **kwargs):
        return None

    with patch.object(
        check_task, "exec_chain", side_effect=mock_exec_chain
    ) as mock_exec_chain_patch:
        task = BaseTask(
            name="main_task",
            readiness_check=[check_task],
            readiness_check_period=0.01,
            readiness_failure_threshold=3,
            readiness_timeout=1,
        )

        # Setup session
        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        # MagicMock task status for check task
        check_status = MagicMock(spec=TaskStatus)
        check_status.is_completed = True
        session.get_task_status.return_value = check_status

        # Setup context and XCom
        ctx = MagicMock(spec=AnyContext)
        with patch.object(task, "get_ctx", return_value=ctx):
            xcom_mock = MagicMock(spec=Xcom)
            ctx.xcom = {"check_task": xcom_mock}

            async def mock_action_coro():
                return None

            action_coro = asyncio.create_task(mock_action_coro())

            # Create a task to run monitor_task_readiness
            monitor_task = asyncio.create_task(
                monitor_task_readiness(task, session, action_coro)
            )

            # Let it run for a bit
            await asyncio.sleep(0.05)

            # Terminate session to stop loop
            session.is_terminated = True
            await monitor_task

            # Verify behavior
            assert mock_exec_chain_patch.called
            assert (
                ctx.log_info.call_count >= 2
            )  # Starting... and at least one "Readiness check OK"


@pytest.mark.asyncio
async def test_monitor_readiness_failure_retry():
    # Setup task with readiness check that fails
    check_task = BaseTask(name="check_task")

    async def mock_exec_chain(*args, **kwargs):
        return None

    with patch.object(
        check_task, "exec_chain", side_effect=mock_exec_chain
    ) as mock_exec_chain_patch, patch(
        "zrb.task.base.monitoring.execute_action_with_retry", new_callable=MagicMock
    ) as mock_execute_retry:

        async def mock_retry_action(*args, **kwargs):
            return None

        mock_execute_retry.side_effect = mock_retry_action

        async def mock_action(ctx):
            return None

        task = BaseTask(
            name="main_task",
            readiness_check=[check_task],
            readiness_check_period=0.01,
            readiness_failure_threshold=1,  # Reduced threshold
            readiness_timeout=1,
            action=mock_action,
        )

        # Setup session
        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        # MagicMock task status
        check_status = MagicMock(spec=TaskStatus)
        check_status.is_completed = False  # Fails
        check_status.is_ready = False

        main_status = MagicMock(spec=TaskStatus)

        def get_task_status(t):
            if t == task:
                return main_status
            return check_status

        session.get_task_status.side_effect = get_task_status

        # Setup context
        ctx = MagicMock(spec=AnyContext)
        with patch.object(task, "get_ctx", return_value=ctx):
            xcom_mock = MagicMock(spec=Xcom)
            ctx.xcom = MagicMock()
            ctx.xcom.get = MagicMock(return_value=xcom_mock)

            # Initial action coro
            action_coro = asyncio.create_task(asyncio.sleep(10))  # Long running task

            # Create a task to run monitor_task_readiness
            monitor_task = asyncio.create_task(
                monitor_task_readiness(task, session, action_coro)
            )

            # Wait for failure threshold to be reached (1 failure * 0.01s period)
            await asyncio.sleep(0.1)

            # Terminate session
            session.is_terminated = True
            await monitor_task

            # Verify cancellation
            assert action_coro.cancelled()

            # Should have reset status
            assert main_status.reset.called

            # Should have deferred a new action
            assert session.defer_action.called

            # Log warning should be present
            ctx.log_warning.assert_any_call("Readiness failure threshold (1) reached.")


@pytest.mark.asyncio
async def test_monitor_readiness_exception():
    # Setup task with readiness check that raises exception
    check_task = BaseTask(name="check_task")

    async def mock_exec_chain(*args, **kwargs):
        raise ValueError("Check failed")

    with patch.object(check_task, "exec_chain", side_effect=mock_exec_chain):
        task = BaseTask(
            name="main_task",
            readiness_check=[check_task],
            readiness_check_period=0.01,
            readiness_failure_threshold=5,
            readiness_timeout=1,
        )

        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        check_status = MagicMock(spec=TaskStatus)
        check_status.is_ready = False
        session.get_task_status.return_value = check_status

        ctx = MagicMock(spec=AnyContext)
        with patch.object(task, "get_ctx", return_value=ctx):
            xcom_mock = MagicMock(spec=Xcom)
            ctx.xcom = MagicMock()
            ctx.xcom.get = MagicMock(return_value=xcom_mock)

            action_coro = asyncio.create_task(asyncio.sleep(0.1))

            monitor_task = asyncio.create_task(
                monitor_task_readiness(task, session, action_coro)
            )

            await asyncio.sleep(0.05)
            session.is_terminated = True
            await monitor_task

            # Verify error logging
            assert ctx.log_error.called
            assert "Readiness check failed with exception" in str(
                ctx.log_error.call_args
            )
            assert check_status.mark_as_failed.called
