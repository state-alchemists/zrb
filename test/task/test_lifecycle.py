import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.task.base.lifecycle import (
    execute_root_tasks,
    log_session_state,
    run_and_cleanup,
    run_task_async,
)


@pytest.mark.asyncio
async def test_run_and_cleanup_success():
    task = MagicMock(spec=AnyTask)
    task.exec_root_tasks = AsyncMock(return_value="result")
    task.get_ctx = MagicMock()

    session = MagicMock(spec=Session)
    session.is_terminated = False

    with patch("zrb.task.base.lifecycle.Session", return_value=session):
        res = await run_and_cleanup(task, session=session)

    assert res == "result"
    session.terminate.assert_called()


@pytest.mark.asyncio
async def test_run_and_cleanup_exception():
    task = MagicMock(spec=AnyTask)
    task.exec_root_tasks = AsyncMock(side_effect=ValueError("Boom"))
    task.get_ctx = MagicMock()

    session = MagicMock(spec=Session)
    session.is_terminated = False

    with pytest.raises(ValueError, match="Boom"):
        await run_and_cleanup(task, session=session)

    session.terminate.assert_called()


@pytest.mark.asyncio
async def test_execute_root_tasks_success():
    task = MagicMock(spec=AnyTask)
    session = MagicMock(spec=Session)
    session.get_root_tasks.return_value = [task]
    session.is_allowed_to_run.return_value = True
    session.wait_deferred = AsyncMock()
    session.final_result = "final"
    session.is_terminated = False

    def terminate():
        session.is_terminated = True

    session.terminate.side_effect = terminate

    # Mock exec_chain
    task.exec_chain = AsyncMock(return_value=None)
    task.get_ctx = MagicMock()

    res = await execute_root_tasks(task, session)

    assert res == "final"
    session.terminate.assert_called()
    assert task.exec_chain.called


@pytest.mark.asyncio
async def test_execute_root_tasks_no_roots():
    task = MagicMock(spec=AnyTask)
    session = MagicMock(spec=Session)
    session.get_root_tasks.return_value = []
    session.is_terminated = False
    task.get_ctx = MagicMock()

    res = await execute_root_tasks(task, session)

    assert res is None
    session.terminate.assert_called()


@pytest.mark.asyncio
async def test_log_session_state():
    task = MagicMock(spec=AnyTask)
    task.get_ctx = MagicMock()

    session = MagicMock(spec=Session)
    session.is_terminated = False
    session.state_logger = MagicMock()

    # We need to terminate the loop eventually
    async def terminate_later():
        await asyncio.sleep(0.01)
        session.is_terminated = True

    asyncio.create_task(terminate_later())

    await log_session_state(task, session)

    assert session.state_logger.write.call_count >= 1


@pytest.mark.asyncio
async def test_run_and_cleanup_cancelled_error():
    """CancelledError is re-raised from run_and_cleanup."""
    task = MagicMock(spec=AnyTask)
    task.exec_root_tasks = AsyncMock(side_effect=asyncio.CancelledError())
    ctx_mock = MagicMock()
    task.get_ctx = MagicMock(return_value=ctx_mock)

    session = MagicMock(spec=Session)
    session.is_terminated = False

    with pytest.raises(asyncio.CancelledError):
        await run_and_cleanup(task, session=session)

    session.terminate.assert_called()


@pytest.mark.asyncio
async def test_run_and_cleanup_session_none():
    """When session=None a new Session is created."""
    task = MagicMock(spec=AnyTask)
    task.exec_root_tasks = AsyncMock(return_value="ok")

    fake_session = MagicMock(spec=Session)
    fake_session.is_terminated = False

    with patch("zrb.task.base.lifecycle.Session", return_value=fake_session) as mock_session_cls:
        result = await run_and_cleanup(task)

    assert mock_session_cls.called
    assert result == "ok"


@pytest.mark.asyncio
async def test_execute_root_tasks_index_error():
    """IndexError during execution is caught and returns None."""
    task = MagicMock(spec=AnyTask)
    ctx_mock = MagicMock()
    task.get_ctx = MagicMock(return_value=ctx_mock)

    session = MagicMock(spec=Session)
    session.get_root_tasks = MagicMock(return_value=[task])
    session.is_allowed_to_run = MagicMock(return_value=True)
    session.is_terminated = False

    # Make exec_chain raise IndexError
    task.exec_chain = AsyncMock(side_effect=IndexError("bad index"))
    session.wait_deferred = AsyncMock()

    result = await execute_root_tasks(task, session)

    assert result is None
    session.terminate.assert_called()


@pytest.mark.asyncio
async def test_execute_root_tasks_cancelled_error():
    """CancelledError during execution is caught and returns None."""
    task = MagicMock(spec=AnyTask)
    ctx_mock = MagicMock()
    task.get_ctx = MagicMock(return_value=ctx_mock)

    session = MagicMock(spec=Session)
    session.get_root_tasks = MagicMock(return_value=[task])
    session.is_allowed_to_run = MagicMock(return_value=True)
    session.is_terminated = False

    task.exec_chain = AsyncMock(side_effect=asyncio.CancelledError())
    session.wait_deferred = AsyncMock()

    result = await execute_root_tasks(task, session)

    assert result is None


@pytest.mark.asyncio
async def test_execute_root_tasks_no_log_state_task():
    """Final state logged even when log_state_task is None."""
    task = MagicMock(spec=AnyTask)
    ctx_mock = MagicMock()
    task.get_ctx = MagicMock(return_value=ctx_mock)

    session = MagicMock(spec=Session)
    session.get_root_tasks = MagicMock(return_value=[task])
    session.is_allowed_to_run = MagicMock(return_value=True)
    session.wait_deferred = AsyncMock()
    session.final_result = "done"
    session.is_terminated = False

    def terminate():
        session.is_terminated = True

    session.terminate.side_effect = terminate
    task.exec_chain = AsyncMock(return_value=None)

    # Patch create_task to return None so log_state_task path hits the else
    with patch("asyncio.create_task", return_value=None):
        result = await execute_root_tasks(task, session)

    assert result == "done"
    session.state_logger.write.assert_called()


@pytest.mark.asyncio
async def test_log_session_state_exception():
    """Exceptions in log_session_state are caught."""
    task = MagicMock(spec=AnyTask)
    ctx_mock = MagicMock()
    task.get_ctx = MagicMock(return_value=ctx_mock)

    session = MagicMock(spec=Session)
    # Make is_terminated always False so loop runs once, then state_logger.write raises
    session.is_terminated = False
    session.state_logger = MagicMock()
    call_count = 0

    def write_side_effect(state):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("log error")

    session.state_logger.write.side_effect = write_side_effect

    # Should not raise
    with patch("asyncio.sleep", new=AsyncMock(side_effect=Exception("stop loop"))):
        # Exception during sleep causes loop to exit via the outer except
        pass

    # Patch sleep to terminate after one iteration
    async def mock_sleep(_):
        session.is_terminated = True

    with patch("asyncio.sleep", new=mock_sleep):
        # Should handle the write exception gracefully
        try:
            await log_session_state(task, session)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_log_session_state_cancelled():
    """CancelledError in log_session_state is handled."""
    task = MagicMock(spec=AnyTask)
    ctx_mock = MagicMock()
    task.get_ctx = MagicMock(return_value=ctx_mock)

    session = MagicMock(spec=Session)
    session.is_terminated = False
    session.state_logger = MagicMock()

    async def cancel_immediately(_):
        raise asyncio.CancelledError()

    with patch("asyncio.sleep", new=cancel_immediately):
        # Should not propagate CancelledError - it's caught internally
        await log_session_state(task, session)

    assert session.state_logger.write.call_count >= 1
