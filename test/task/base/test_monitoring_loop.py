"""Tests for task/base/monitoring.py - BaseTaskMonitoring.monitor_task_readiness."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.session.any_session import AnySession
from zrb.task.base.base_task import BaseTask
from zrb.task.base.execution import BaseTaskExecution
from zrb.task.base.monitoring import BaseTaskMonitoring
from zrb.task_status.task_status import TaskStatus


def _make_ctx():
    ctx = MagicMock(spec=AnyContext)
    ctx.xcom = MagicMock()
    ctx.xcom.get.return_value = None
    return ctx


def _make_task_status(is_completed=True, is_ready=True):
    status = MagicMock(spec=TaskStatus)
    status.is_completed = is_completed
    status.is_ready = is_ready
    return status


class TestMonitorTaskReadinessException:
    """Test monitor_task_readiness when a general exception occurs."""

    @pytest.mark.asyncio
    async def test_general_exception_increments_failure_count(self):
        """General exception increments failure_count and marks check as failed."""
        task = BaseTask(name="test_task")
        monitoring = BaseTaskMonitoring(task, BaseTaskExecution(task))
        check_task = BaseTask(name="check_task")
        check_task.exec_chain = MagicMock(return_value=None)
        task.append_readiness_check(check_task)
        task.readiness_failure_threshold = 99

        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        check_status = _make_task_status(is_completed=False, is_ready=False)
        session.get_task_status.return_value = check_status

        ctx = _make_ctx()
        action_coro = MagicMock(spec=asyncio.Task)

        call_count = 0

        async def mock_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                session.is_terminated = True

        mock_run_async = MagicMock(return_value=None)

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                with patch(
                    "zrb.task.base.monitoring.gather_fail_fast",
                    side_effect=RuntimeError("check failed"),
                ):
                    with patch(
                        "zrb.task.base.monitoring.run_async", new=mock_run_async
                    ):
                        await monitoring.monitor_task_readiness(session, action_coro)

        assert ctx.log_error.called
        error_calls = [str(c) for c in ctx.log_error.call_args_list]
        assert any(
            "exception" in c.lower() or "failed" in c.lower() for c in error_calls
        )


class TestMonitorTaskReadinessChecksNotCompleted:
    """Test when checks don't complete (tasks not in completed state)."""

    @pytest.mark.asyncio
    async def test_checks_not_completed_increments_failure_count(self):
        """If wait_for succeeds but tasks aren't in completed state, increment failure."""
        task = BaseTask(name="test_task")
        monitoring = BaseTaskMonitoring(task, BaseTaskExecution(task))
        check_task = BaseTask(name="check_task")
        check_task.exec_chain = MagicMock(return_value=None)
        task.append_readiness_check(check_task)
        task.readiness_failure_threshold = 99

        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        check_status = _make_task_status(is_completed=False, is_ready=False)
        session.get_task_status.return_value = check_status

        ctx = _make_ctx()
        action_coro = MagicMock(spec=asyncio.Task)

        call_count = 0

        async def mock_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                session.is_terminated = True

        mock_run_async = MagicMock(return_value=None)

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                with patch(
                    "zrb.task.base.monitoring.gather_fail_fast",
                    new=MagicMock(return_value=None),
                ):
                    with patch("asyncio.wait_for", new=AsyncMock(return_value=None)):
                        with patch(
                            "zrb.task.base.monitoring.run_async", new=mock_run_async
                        ):
                            await monitoring.monitor_task_readiness(
                                session, action_coro
                            )

        assert ctx.log_warning.called
        warning_calls = [str(c) for c in ctx.log_warning.call_args_list]
        assert any("did not complete" in c for c in warning_calls)


class TestMonitorTaskReadinessThresholdReached:
    """Test monitor_task_readiness reaches failure threshold and handles it properly."""

    @pytest.mark.asyncio
    async def test_threshold_reached_action_already_done(self):
        """Threshold reached but action already done — no cancellation needed."""
        task = BaseTask(name="test_task")
        monitoring = BaseTaskMonitoring(task, BaseTaskExecution(task))
        check_task = BaseTask(name="check_task")
        check_task.exec_chain = MagicMock(return_value=None)
        task.append_readiness_check(check_task)
        task.readiness_failure_threshold = 1

        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        check_status = _make_task_status(is_completed=False, is_ready=False)
        task_status = _make_task_status()
        session.get_task_status.side_effect = lambda t: (
            check_status if t is check_task else task_status
        )

        ctx = _make_ctx()
        action_coro = MagicMock(spec=asyncio.Task)
        action_coro.done.return_value = True

        call_count = 0

        async def mock_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                session.is_terminated = True

        mock_new_task = MagicMock(spec=asyncio.Task)
        mock_run_async = MagicMock(return_value=None)
        mock_exec = MagicMock(return_value=None)

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                with patch(
                    "zrb.task.base.monitoring.gather_fail_fast",
                    side_effect=asyncio.TimeoutError,
                ):
                    with patch(
                        "zrb.task.base.monitoring.run_async", new=mock_run_async
                    ):
                        with patch("asyncio.create_task", return_value=mock_new_task):
                            with patch.object(
                                BaseTaskExecution,
                                "execute_action_with_retry",
                                new=mock_exec,
                            ):
                                await monitoring.monitor_task_readiness(
                                    session, action_coro
                                )

        # action_coro.done() was True so cancel should not be called
        action_coro.cancel.assert_not_called()


class TestMonitorThresholdReachedActionErrorsOnCancel:
    """The action's own error while unwinding from cancellation must not
    propagate (the retry loop already logged/handled it) but the swallow
    itself must now be observable via ctx.log_debug."""

    @pytest.mark.asyncio
    async def test_action_exception_during_cancel_is_logged_not_silenced(self):
        task = BaseTask(name="test_task")
        monitoring = BaseTaskMonitoring(task, BaseTaskExecution(task))
        check_task = BaseTask(name="check_task")
        check_task.exec_chain = MagicMock(return_value=None)
        task.append_readiness_check(check_task)
        task.readiness_failure_threshold = 1

        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        check_status = _make_task_status(is_completed=False, is_ready=False)
        task_status = _make_task_status()
        session.get_task_status.side_effect = lambda t: (
            check_status if t is check_task else task_status
        )

        ctx = _make_ctx()

        async def action_that_errors_on_cancel():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                # The action's own unwind fails with a real error instead of
                # a clean CancelledError propagation.
                raise RuntimeError("action's own cleanup failed")

        action_coro = asyncio.create_task(action_that_errors_on_cancel())
        # Let the action actually reach its await point before the monitor
        # cancels it — cancelling a not-yet-started task delivers a clean
        # CancelledError without ever running its try/except.
        await asyncio.sleep(0)

        call_count = 0

        async def mock_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                session.is_terminated = True

        mock_new_task = MagicMock(spec=asyncio.Task)
        mock_run_async = MagicMock(return_value=None)
        mock_exec = MagicMock(return_value=None)

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                with patch(
                    "zrb.task.base.monitoring.gather_fail_fast",
                    side_effect=asyncio.TimeoutError,
                ):
                    with patch(
                        "zrb.task.base.monitoring.run_async", new=mock_run_async
                    ):
                        with patch("asyncio.create_task", return_value=mock_new_task):
                            with patch.object(
                                BaseTaskExecution,
                                "execute_action_with_retry",
                                new=mock_exec,
                            ):
                                await asyncio.wait_for(
                                    monitoring.monitor_task_readiness(
                                        session, action_coro
                                    ),
                                    timeout=5,
                                )

        assert ctx.log_debug.called
        debug_calls = [str(c) for c in ctx.log_debug.call_args_list]
        assert any("action's own cleanup failed" in c for c in debug_calls)


class TestMonitorOwnCancellation:
    """The monitor must not swallow ITS OWN cancellation while reaping the action."""

    @pytest.mark.asyncio
    async def test_monitor_cancel_during_action_reap_propagates(self):
        """Cancelling the monitor while it awaits the cancelled action must
        propagate — swallowing it restarts the action after shutdown."""
        check_task = BaseTask(name="check_task")
        check_task.exec_chain = AsyncMock(side_effect=ValueError("service down"))
        task = BaseTask(
            name="test_task",
            readiness_check=[check_task],
            readiness_check_period=0.01,
            readiness_failure_threshold=1,
            readiness_timeout=5,
        )
        monitoring = BaseTaskMonitoring(task, BaseTaskExecution(task))

        session = MagicMock(spec=AnySession)
        session.is_terminated = False
        session.get_task_status.side_effect = lambda t: _make_task_status()
        ctx = _make_ctx()

        started_cleanup = asyncio.Event()

        async def stubborn_action():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                started_cleanup.set()
                await asyncio.sleep(30)  # slow cleanup keeps the monitor waiting
                raise

        action = asyncio.create_task(stubborn_action())
        mock_exec = MagicMock(return_value=None)

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch.object(
                BaseTaskExecution, "execute_action_with_retry", new=mock_exec
            ):
                monitor = asyncio.create_task(
                    monitoring.monitor_task_readiness(session, action)
                )
                # Wait until the monitor cancelled the action and is reaping it.
                await asyncio.wait_for(started_cleanup.wait(), timeout=5)
                monitor.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(monitor, timeout=5)

        # The action was never restarted after the monitor's cancellation.
        mock_exec.assert_not_called()
        action.cancel()
        try:
            await action
        except asyncio.CancelledError:
            pass
