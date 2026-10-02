from unittest.mock import MagicMock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.session.any_session import AnySession
from zrb.task.base.base_task import BaseTask
from zrb.task.base.execution import BaseTaskExecution
from zrb.task_status.task_status import TaskStatus
from zrb.xcom.xcom import Xcom


@pytest.mark.asyncio
async def test_execute_action_with_retry_success():

    async def mock_action(ctx):
        return "ok"

    # Set __name__ attribute on the function
    mock_action.__name__ = "mock_action"

    task = BaseTask(name="task", retries=1, retry_period=0, action=mock_action)
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    status = MagicMock(spec=TaskStatus)
    session.get_task_status.return_value = status

    ctx = MagicMock(spec=AnyContext)
    with patch.object(task, "get_ctx", return_value=ctx):
        # Fix: Use a MagicMock that behaves like a dict but also has methods if needed
        xcom_mock = MagicMock(spec=Xcom)
        # Configure ctx.xcom.get to return our mock xcom
        ctx.xcom = MagicMock()
        ctx.xcom.get.return_value = xcom_mock

        result = await execution.execute_action_with_retry(session)

        assert result == "ok"
        assert status.mark_as_completed.called
        xcom_mock.push.assert_called_with("ok")


@pytest.mark.asyncio
async def test_execute_action_with_retry_failure():

    async def mock_action(ctx):
        raise Exception("boom")

    # Set __name__ attribute on the function
    mock_action.__name__ = "mock_action"

    task = BaseTask(name="task", retries=0, retry_period=0, action=mock_action)
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    status = MagicMock(spec=TaskStatus)
    session.get_task_status.return_value = status

    ctx = MagicMock(spec=AnyContext)
    with patch.object(task, "get_ctx", return_value=ctx):
        with pytest.raises(Exception, match="boom"):
            await execution.execute_action_with_retry(session)

        assert status.mark_as_failed.called
        assert status.mark_as_permanently_failed.called

        # The full traceback goes to log_debug (silent at default log level),
        # never to log_error, so a permanently-failed task doesn't dump a raw
        # traceback to the console by default.
        assert any(
            "Traceback (most recent call last)" in call.args[0]
            for call in ctx.log_debug.call_args_list
        )
        for call in ctx.log_error.call_args_list:
            assert "Traceback (most recent call last)" not in call.args[0]


@pytest.mark.asyncio
async def test_system_exit_is_not_retried_as_a_task_failure():
    """`sys.exit()` in an action body stops the run, it is not a failed attempt.

    Regression: `SystemExit` fell into the generic `except BaseException`, so a
    deliberate exit was logged as `Attempt 1/N failed: 1` -- printing the exit
    *code* where the error message goes -- retried up to `retries` times, and
    then reported as permanently failed. It now passes through alongside the
    other control-flow exceptions, like a refused insecure server bind does.
    """
    attempts = 0

    async def mock_action(ctx):
        nonlocal attempts
        attempts += 1
        raise SystemExit(1)

    mock_action.__name__ = "mock_action"

    task = BaseTask(name="task", retries=2, retry_period=0, action=mock_action)
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    status = MagicMock(spec=TaskStatus)
    session.get_task_status.return_value = status

    ctx = MagicMock(spec=AnyContext)
    with patch.object(task, "get_ctx", return_value=ctx):
        with pytest.raises(SystemExit) as exc_info:
            await execution.execute_action_with_retry(session)

    assert exc_info.value.code == 1
    assert attempts == 1, "SystemExit must not be retried"
    assert not status.mark_as_permanently_failed.called


@pytest.mark.asyncio
async def test_failing_successor_neither_reruns_action_nor_is_swallowed():
    """A successor's failure propagates without retrying the parent.

    The parent's action already succeeded; re-running it (a deploy, a
    migration) is the wrong response to a notification step failing, and the
    parent's fallbacks answer the parent's own failure only.
    """
    calls = {"parent": 0, "fallback": 0}

    def parent_action(ctx):
        calls["parent"] += 1
        return "deployed"

    def failing_successor(ctx):
        raise RuntimeError("successor failed")

    def fallback_action(ctx):
        calls["fallback"] += 1

    parent = BaseTask(name="parent", action=parent_action, retries=2, retry_period=0)
    parent.append_successor(
        BaseTask(name="notify", action=failing_successor, retries=0)
    )
    parent.append_fallback(BaseTask(name="rollback", action=fallback_action))

    with pytest.raises(RuntimeError, match="successor failed"):
        await parent.async_run()

    assert calls == {"parent": 1, "fallback": 0}
