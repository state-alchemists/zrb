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
