"""Readiness against an action that fails: the action's failure wins."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.session.any_session import AnySession
from zrb.task.base.base_task import BaseTask
from zrb.task.base.execution import BaseTaskExecution
from zrb.task_status.task_status import TaskStatus


@pytest.mark.asyncio
async def test_action_failure_fails_task_without_waiting_out_readiness_timeout():
    """An action that fails permanently ends the readiness wait at once."""
    never = asyncio.Event()
    polling_cancelled = asyncio.Event()

    async def poll_forever(_session):
        try:
            await never.wait()
        except asyncio.CancelledError:
            polling_cancelled.set()
            raise

    polling_check = BaseTask(name="polling_check")
    polling_check.exec_chain = poll_forever

    task = BaseTask(
        name="task",
        readiness_check=polling_check,
        readiness_check_delay=0,
        readiness_timeout=30,
    )
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    session.is_terminated = False

    ctx = MagicMock(spec=AnyContext)
    task_status = MagicMock(spec=TaskStatus)
    task_status.is_permanently_failed = True
    task_status.is_completed = False
    session.get_task_status.side_effect = lambda t: (
        task_status if t is task else MagicMock(spec=TaskStatus)
    )

    with patch.object(task, "get_ctx", return_value=ctx):
        with patch.object(
            execution,
            "execute_action_with_retry",
            new=AsyncMock(side_effect=RuntimeError("bind failed")),
        ):
            with pytest.raises(RuntimeError, match="bind failed"):
                await asyncio.wait_for(
                    execution.execute_action_until_ready(session), timeout=5
                )

    assert polling_cancelled.is_set()
    task_status.mark_as_ready.assert_not_called()
    session.defer_action.assert_not_called()


@pytest.mark.asyncio
async def test_action_failing_as_its_checks_pass_is_never_marked_ready():
    """A check and the action finishing in the same round: the action's
    failure wins, whatever the check reported."""
    check_passed = asyncio.Event()

    async def pass_check(_session):
        check_passed.set()

    async def crash_once_the_check_passes(_session):
        await check_passed.wait()
        raise RuntimeError("crashed on start")

    passing_check = BaseTask(name="passing_check")
    passing_check.exec_chain = pass_check

    task = BaseTask(
        name="task",
        readiness_check=passing_check,
        readiness_check_delay=0,
        readiness_timeout=30,
    )
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    session.is_terminated = False

    ctx = MagicMock(spec=AnyContext)
    task_status = MagicMock(spec=TaskStatus)
    task_status.is_permanently_failed = True
    task_status.is_completed = False
    check_status = MagicMock(spec=TaskStatus)
    check_status.is_completed = True
    session.get_task_status.side_effect = lambda t: (
        task_status if t is task else check_status
    )

    with patch.object(task, "get_ctx", return_value=ctx):
        with patch.object(
            execution,
            "execute_action_with_retry",
            new=crash_once_the_check_passes,
        ):
            with pytest.raises(RuntimeError, match="crashed on start"):
                await asyncio.wait_for(
                    execution.execute_action_until_ready(session), timeout=5
                )

    task_status.mark_as_ready.assert_not_called()
    session.defer_action.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("ticks", range(8))
async def test_a_check_failing_with_the_action_leaves_no_unretrieved_exception(
    ticks,
):
    """The action's failure wins, and the check's failure is still consumed.

    `ticks` sweeps when the action fails relative to the check.
    """
    import gc

    async def failing_check(_session):
        raise RuntimeError("check broke")

    async def failing_action(_session):
        for _ in range(ticks):
            await asyncio.sleep(0)
        raise RuntimeError("crashed on start")

    check = BaseTask(name="failing_check", retries=0)
    check.exec_chain = failing_check
    task = BaseTask(
        name="task",
        readiness_check=check,
        readiness_check_delay=0,
        readiness_timeout=30,
    )
    execution = BaseTaskExecution(task)
    session = MagicMock(spec=AnySession)
    session.is_terminated = False
    task_status = MagicMock(spec=TaskStatus)
    task_status.is_permanently_failed = True
    session.get_task_status.return_value = task_status

    unretrieved = []
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(lambda _loop, context: unretrieved.append(context))
    try:
        with patch.object(task, "get_ctx", return_value=MagicMock(spec=AnyContext)):
            with patch.object(
                execution, "execute_action_with_retry", new=failing_action
            ):
                with pytest.raises(RuntimeError):
                    await execution.execute_action_until_ready(session)
        gc.collect()
        await asyncio.sleep(0)
    finally:
        loop.set_exception_handler(None)

    assert unretrieved == []
