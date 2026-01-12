import asyncio
from unittest.mock import MagicMock, Mock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.session.any_session import AnySession
from zrb.task.base.execution import (
    execute_action_until_ready,
    execute_action_with_retry,
    execute_fallbacks,
    execute_successors,
    execute_task_action,
    execute_task_chain,
    run_default_action,
)
from zrb.task.base_task import BaseTask
from zrb.task_status.task_status import TaskStatus
from zrb.xcom.xcom import Xcom


@pytest.mark.asyncio
async def test_execute_task_chain_not_allowed():
    task = BaseTask(name="test_task")
    session = Mock(spec=AnySession)
    session.is_terminated = False
    session.is_allowed_to_run.return_value = False

    result = await execute_task_chain(task, session)
    assert result is None
    session.get_next_tasks.assert_not_called()


@pytest.mark.asyncio
async def test_execute_task_chain_success():
    task = BaseTask(name="test_task")
    session = Mock(spec=AnySession)
    session.is_terminated = False
    session.is_allowed_to_run.return_value = True

    # Mock execute_task_action
    async def mock_execute_task_action(task, session):
        return "success"
    
    with patch(
        "zrb.task.base.execution.execute_task_action", side_effect=mock_execute_task_action
    ) as mock_action_patch:

        # Next tasks
        next_task = BaseTask(name="next_task")
        
        async def mock_exec_chain(session):
            return None
        
        with patch.object(next_task, "exec_chain", side_effect=mock_exec_chain) as mock_exec_chain_patch:
            session.get_next_tasks.return_value = [next_task]

            result = await execute_task_chain(task, session)

            assert result == "success"
            assert mock_exec_chain_patch.called


@pytest.mark.asyncio
async def test_execute_task_action_condition_false():
    task = BaseTask(name="test_task", execute_condition=False)
    
    session = Mock(spec=AnySession)
    session.is_allowed_to_run.return_value = True
    status = Mock(spec=TaskStatus)
    session.get_task_status.return_value = status

    with patch("zrb.task.base.execution.get_bool_attr", return_value=False):
        await execute_task_action(task, session)
        assert status.mark_as_skipped.called


@pytest.mark.asyncio
async def test_execute_action_until_ready_no_checks():
    task = BaseTask(name="test_task")
    session = Mock(spec=AnySession)
    status = Mock(spec=TaskStatus)
    status.is_completed = True
    session.get_task_status.return_value = status

    # Save original function
    import zrb.task.base.execution
    original_execute_action_with_retry = zrb.task.base.execution.execute_action_with_retry
    
    try:
        # Replace with mock
        async def mock_execute_action_with_retry(task, session):
            return "done"
        
        zrb.task.base.execution.execute_action_with_retry = mock_execute_action_with_retry
        
        result = await execute_action_until_ready(task, session)

        assert result == "done"
        assert status.mark_as_ready.called
    finally:
        # Restore original function
        zrb.task.base.execution.execute_action_with_retry = original_execute_action_with_retry


@pytest.mark.asyncio
async def test_execute_action_with_retry_success():
    
    async def mock_action(ctx):
        return "ok"
    
    # Set __name__ attribute on the function
    mock_action.__name__ = "mock_action"
    
    task = BaseTask(name="task", retries=1, retry_period=0, action=mock_action)
    
    session = Mock(spec=AnySession)
    status = Mock(spec=TaskStatus)
    session.get_task_status.return_value = status

    ctx = Mock(spec=AnyContext)
    with patch.object(task, "get_ctx", return_value=ctx):
        # Fix: Use a Mock that behaves like a dict but also has methods if needed
        xcom_mock = Mock(spec=Xcom)
        # Configure ctx.xcom.get to return our mock xcom
        ctx.xcom = Mock()
        ctx.xcom.get.return_value = xcom_mock

        result = await execute_action_with_retry(task, session)

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
    
    session = Mock(spec=AnySession)
    status = Mock(spec=TaskStatus)
    session.get_task_status.return_value = status

    ctx = Mock(spec=AnyContext)
    with patch.object(task, "get_ctx", return_value=ctx):
        with pytest.raises(Exception, match="boom"):
            await execute_action_with_retry(task, session)

        assert status.mark_as_failed.called
        assert status.mark_as_permanently_failed.called


@pytest.mark.asyncio
async def test_run_default_action_callable():
    ctx = Mock(spec=AnyContext)
    
    async def mock_action(ctx):
        return "result"
    
    # Set __name__ attribute on the function
    mock_action.__name__ = "mock_action"
    
    task = BaseTask(name="task", action=mock_action)

    result = await run_default_action(task, ctx)
    assert result == "result"


@pytest.mark.asyncio
async def test_execute_successors():
    s1 = BaseTask(name="s1")
    
    async def mock_exec_chain(session):
        return None
    
    with patch.object(s1, "exec_chain", side_effect=mock_exec_chain) as mock_exec_chain_patch:
        task = BaseTask(name="task", successor=[s1])
        session = Mock(spec=AnySession)
        await execute_successors(task, session)
        assert mock_exec_chain_patch.called


@pytest.mark.asyncio
async def test_execute_fallbacks():
    f1 = BaseTask(name="f1")
    
    async def mock_exec_chain(session):
        return None
    
    with patch.object(f1, "exec_chain", side_effect=mock_exec_chain) as mock_exec_chain_patch:
        task = BaseTask(name="task", fallback=[f1])
        session = Mock(spec=AnySession)
        await execute_fallbacks(task, session)
        assert mock_exec_chain_patch.called