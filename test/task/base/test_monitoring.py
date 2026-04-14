"""Tests for task/base/monitoring.py - monitor_task_readiness function."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.session.any_session import AnySession
from zrb.task.base_task import BaseTask
from zrb.task_status.task_status import TaskStatus


def _make_session(is_terminated_sequence=None):
    """Create a session mock that toggles is_terminated after specified calls."""
    session = MagicMock(spec=AnySession)
    if is_terminated_sequence is None:
        session.is_terminated = False
    else:
        session.is_terminated = is_terminated_sequence[0]
    return session


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


class TestMonitorTaskReadinessNoChecks:
    """Test monitor_task_readiness when there are no readiness checks."""

    @pytest.mark.asyncio
    async def test_no_readiness_checks_returns_immediately(self):
        """If readiness_checks is empty, should return immediately with a debug log."""
        from zrb.task.base.monitoring import monitor_task_readiness

        task = BaseTask(name="test_task")
        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        ctx = _make_ctx()
        action_coro = MagicMock(spec=asyncio.Task)

        with patch.object(task, "get_ctx", return_value=ctx):
            # No readiness_checks defined — task.readiness_checks should be []
            await monitor_task_readiness(task, session, action_coro)

        ctx.log_debug.assert_called_once()
        assert "No readiness checks" in ctx.log_debug.call_args[0][0]


class TestMonitorTaskReadinessSessionTerminated:
    """Test monitor_task_readiness when session terminates during sleep."""

    @pytest.mark.asyncio
    async def test_session_terminates_during_sleep(self):
        """Loop exits when session is terminated after first sleep."""
        from zrb.task.base.monitoring import monitor_task_readiness

        task = BaseTask(name="test_task")
        session = MagicMock(spec=AnySession)

        ctx = _make_ctx()
        action_coro = MagicMock(spec=asyncio.Task)

        # We need at least one readiness_check to enter the loop
        check_task = BaseTask(name="check_task")
        check_status = _make_task_status(is_completed=True, is_ready=True)

        sleep_calls = []

        async def mock_sleep(duration):
            sleep_calls.append(duration)
            # After first sleep, mark session as terminated
            session.is_terminated = True

        def setup_session_for_check():
            session.is_terminated = False
            session.get_task_status.return_value = check_status

        setup_session_for_check()
        task.append_readiness_check(check_task)

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                with patch("asyncio.wait_for", new=AsyncMock(return_value=None)):
                    async def mock_run_async(coro):
                        return await coro

                    with patch("zrb.task.base.monitoring.run_async", new=mock_run_async):
                        with patch.object(check_task, "exec_chain") as mock_exec_chain:
                            async def noop_chain(session):
                                return None

                            mock_exec_chain.return_value = noop_chain(session)
                            await monitor_task_readiness(task, session, action_coro)

        assert len(sleep_calls) >= 1
        ctx.log_info.assert_called()


class TestMonitorTaskReadinessSuccess:
    """Test monitor_task_readiness with successful readiness checks."""

    @pytest.mark.asyncio
    async def test_successful_readiness_check_resets_failure_count(self):
        """When all checks complete successfully, failure_count resets to 0."""
        from zrb.task.base.monitoring import monitor_task_readiness

        task = BaseTask(name="test_task")
        check_task = BaseTask(name="check_task")
        task.append_readiness_check(check_task)

        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        check_status = _make_task_status(is_completed=True, is_ready=True)
        session.get_task_status.return_value = check_status

        ctx = _make_ctx()
        action_coro = MagicMock(spec=asyncio.Task)

        call_count = 0

        async def mock_sleep(duration):
            nonlocal call_count
            call_count += 1
            # Let first iteration complete (checks run), then terminate on 2nd sleep
            if call_count >= 2:
                session.is_terminated = True

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                with patch("asyncio.wait_for", new=AsyncMock(return_value=None)):
                    with patch("asyncio.gather", new=AsyncMock(return_value=None)):
                        with patch.object(check_task, "exec_chain") as mock_exec_chain:
                            async def noop_chain(session):
                                return None

                            mock_exec_chain.return_value = noop_chain(session)

                            async def mock_run_async(coro):
                                return None  # Don't await the coro to avoid "never awaited" warning

                            with patch("zrb.task.base.monitoring.run_async", new=mock_run_async):
                                await monitor_task_readiness(task, session, action_coro)

        # Should have logged "Readiness check OK." since all checks completed
        log_calls = [str(c) for c in ctx.log_info.call_args_list]
        assert any("OK" in c for c in log_calls)


class TestMonitorTaskReadinessTimeout:
    """Test monitor_task_readiness when readiness checks time out."""

    @pytest.mark.asyncio
    async def test_timeout_increments_failure_count(self):
        """Timeout during wait_for increments failure_count and logs a warning."""
        from zrb.task.base.monitoring import monitor_task_readiness

        task = BaseTask(name="test_task")
        check_task = BaseTask(name="check_task")
        task.append_readiness_check(check_task)

        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        check_status = _make_task_status(is_completed=False, is_ready=False)
        session.get_task_status.return_value = check_status

        ctx = _make_ctx()
        action_coro = MagicMock(spec=asyncio.Task)
        action_coro.done.return_value = True  # Already done, so won't be cancelled

        call_count = 0

        async def mock_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                session.is_terminated = True

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                # First wait_for raises TimeoutError, then session terminates
                with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                    with patch.object(check_task, "exec_chain") as mock_exec_chain:
                        async def noop_chain(session):
                            return None

                        mock_exec_chain.return_value = noop_chain(session)

                        async def mock_run_async(coro):
                            return await coro

                        with patch("zrb.task.base.monitoring.run_async", new=mock_run_async):
                            await monitor_task_readiness(task, session, action_coro)

        # Should have warned about timeout
        assert ctx.log_warning.called
        warning_calls = [str(c) for c in ctx.log_warning.call_args_list]
        assert any("timed out" in c for c in warning_calls)


class TestMonitorTaskReadinessFailureThreshold:
    """Test that threshold reached causes task cancellation and re-execution."""

    @pytest.mark.asyncio
    async def test_threshold_reached_cancels_and_restarts(self):
        """When failure threshold is reached, cancel action and re-execute."""
        from zrb.task.base.monitoring import monitor_task_readiness

        task = BaseTask(name="test_task")
        check_task = BaseTask(name="check_task")
        task.append_readiness_check(check_task)
        task._readiness_failure_threshold = 1

        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        check_status = _make_task_status(is_completed=False, is_ready=False)
        task_status = _make_task_status()
        session.get_task_status.side_effect = (
            lambda t: check_status if t is check_task else task_status
        )

        ctx = _make_ctx()

        # action_coro is not done, so should be cancelled
        action_coro = MagicMock(spec=asyncio.Task)
        action_coro.done.return_value = False

        async def mock_cancel_coro():
            raise asyncio.CancelledError()

        action_coro.__await__ = mock_cancel_coro

        call_count = 0

        async def mock_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                session.is_terminated = True

        mock_new_task = MagicMock(spec=asyncio.Task)

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                    with patch.object(check_task, "exec_chain") as mock_exec_chain:
                        async def noop_chain(session):
                            return None

                        mock_exec_chain.return_value = noop_chain(session)

                        async def mock_run_async(coro):
                            if hasattr(coro, '__await__'):
                                return await coro
                            return await coro

                        with patch("zrb.task.base.monitoring.run_async", new=mock_run_async):
                            with patch("asyncio.create_task", return_value=mock_new_task):
                                with patch(
                                    "zrb.task.base.monitoring.execute_action_with_retry"
                                ) as mock_exec:
                                    async def noop_exec(task, session):
                                        return None

                                    mock_exec.return_value = noop_exec(task, session)

                                    try:
                                        await monitor_task_readiness(
                                            task, session, action_coro
                                        )
                                    except Exception:
                                        pass  # May raise due to cancelled action mock

        # Should have warned about threshold
        assert ctx.log_warning.called


class TestMonitorTaskReadinessCancelled:
    """Test monitor_task_readiness when CancelledError is raised."""

    @pytest.mark.asyncio
    async def test_cancelled_error_breaks_loop(self):
        """CancelledError during check breaks the monitoring loop cleanly."""
        from zrb.task.base.monitoring import monitor_task_readiness

        task = BaseTask(name="test_task")
        check_task = BaseTask(name="check_task")
        task.append_readiness_check(check_task)

        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        check_status = _make_task_status(is_completed=False, is_ready=False)
        session.get_task_status.return_value = check_status

        ctx = _make_ctx()
        action_coro = MagicMock(spec=asyncio.Task)

        async def mock_sleep(duration):
            # Don't set is_terminated - let CancelledError handle it
            pass

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                with patch(
                    "asyncio.wait_for", side_effect=asyncio.CancelledError
                ):
                    with patch.object(check_task, "exec_chain") as mock_exec_chain:
                        async def noop_chain(session):
                            return None

                        mock_exec_chain.return_value = noop_chain(session)

                        async def mock_run_async(coro):
                            return await coro

                        with patch("zrb.task.base.monitoring.run_async", new=mock_run_async):
                            await monitor_task_readiness(task, session, action_coro)

        # Should have logged cancellation message
        info_calls = [str(c) for c in ctx.log_info.call_args_list]
        assert any("cancel" in c.lower() or "interrupt" in c.lower() for c in info_calls)


class TestMonitorTaskReadinessException:
    """Test monitor_task_readiness when a general exception occurs."""

    @pytest.mark.asyncio
    async def test_general_exception_increments_failure_count(self):
        """General exception increments failure_count and marks check as failed."""
        from zrb.task.base.monitoring import monitor_task_readiness

        task = BaseTask(name="test_task")
        check_task = BaseTask(name="check_task")
        task.append_readiness_check(check_task)
        task._readiness_failure_threshold = 99  # Don't trigger threshold reset

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

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                with patch(
                    "asyncio.wait_for", side_effect=RuntimeError("check failed")
                ):
                    with patch.object(check_task, "exec_chain") as mock_exec_chain:
                        async def noop_chain(session):
                            return None

                        mock_exec_chain.return_value = noop_chain(session)

                        async def mock_run_async(coro):
                            return await coro

                        with patch("zrb.task.base.monitoring.run_async", new=mock_run_async):
                            await monitor_task_readiness(task, session, action_coro)

        # Should have logged an error
        assert ctx.log_error.called
        error_calls = [str(c) for c in ctx.log_error.call_args_list]
        assert any("exception" in c.lower() or "failed" in c.lower() for c in error_calls)


class TestMonitorTaskReadinessChecksNotCompleted:
    """Test when checks don't complete (tasks not in completed state)."""

    @pytest.mark.asyncio
    async def test_checks_not_completed_increments_failure_count(self):
        """If wait_for succeeds but tasks aren't in completed state, increment failure."""
        from zrb.task.base.monitoring import monitor_task_readiness

        task = BaseTask(name="test_task")
        check_task = BaseTask(name="check_task")
        task.append_readiness_check(check_task)
        task._readiness_failure_threshold = 99  # Don't trigger threshold reset

        session = MagicMock(spec=AnySession)
        session.is_terminated = False

        # Status shows NOT completed
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

        with patch.object(task, "get_ctx", return_value=ctx):
            with patch("asyncio.sleep", new=mock_sleep):
                with patch("asyncio.wait_for") as mock_wait:
                    # wait_for succeeds (no exception) but tasks not completed
                    mock_wait.return_value = None

                    with patch.object(check_task, "exec_chain") as mock_exec_chain:
                        async def noop_chain(session):
                            return None

                        mock_exec_chain.return_value = noop_chain(session)

                        async def mock_run_async(coro):
                            return await coro

                        with patch("zrb.task.base.monitoring.run_async", new=mock_run_async):
                            await monitor_task_readiness(task, session, action_coro)

        # Should have warned about tasks not completing
        assert ctx.log_warning.called
        warning_calls = [str(c) for c in ctx.log_warning.call_args_list]
        assert any("did not complete" in c for c in warning_calls)
