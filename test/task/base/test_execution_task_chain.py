from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.attr.tpl import Tpl
from zrb.context.any_context import AnyContext
from zrb.session.any_session import AnySession
from zrb.task.base.base_task import BaseTask
from zrb.task.base.execution import BaseTaskExecution
from zrb.task_status.task_status import TaskStatus


@pytest.mark.asyncio
async def test_execute_task_chain_not_allowed():
    task = BaseTask(name="test_task")
    execution = BaseTaskExecution(task)
    session = MagicMock(spec=AnySession)
    session.is_terminated = False
    session.is_allowed_to_run.return_value = False

    result = await execution.execute_task_chain(session)
    assert result is None
    session.get_next_tasks.assert_not_called()


@pytest.mark.asyncio
async def test_execute_task_chain_success():
    task = BaseTask(name="test_task")
    execution = BaseTaskExecution(task)
    session = MagicMock(spec=AnySession)
    session.is_terminated = False
    session.is_allowed_to_run.return_value = True

    mock_execute_task_action = AsyncMock(return_value="success")

    with patch.object(execution, "execute_task_action", new=mock_execute_task_action):
        next_task = BaseTask(name="next_task")
        next_task.exec_chain = AsyncMock(return_value=None)

        session.get_next_tasks.return_value = [next_task]

        result = await execution.execute_task_chain(session)

        assert result == "success"
        assert next_task.exec_chain.called


@pytest.mark.asyncio
async def test_execute_task_action_condition_false():
    task = BaseTask(name="test_task", execute_condition=False)
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    session.is_allowed_to_run.return_value = True
    status = MagicMock(spec=TaskStatus)
    session.get_task_status.return_value = status

    with patch("zrb.task.base.execution.get_bool_attr", return_value=False):
        await execution.execute_task_action(session)
        assert status.mark_as_skipped.called


@pytest.mark.asyncio
async def test_execute_action_until_ready_no_checks():
    task = BaseTask(name="test_task")
    execution = BaseTaskExecution(task)
    session = MagicMock(spec=AnySession)
    status = MagicMock(spec=TaskStatus)
    status.is_completed = True
    session.get_task_status.return_value = status

    with patch.object(
        execution, "execute_action_with_retry", new=AsyncMock(return_value="done")
    ):
        result = await execution.execute_action_until_ready(session)

        assert result == "done"
        assert status.mark_as_ready.called


@pytest.mark.asyncio
async def test_run_default_action_callable():
    ctx = MagicMock(spec=AnyContext)

    async def mock_action(ctx):
        return "result"

    # Set __name__ attribute on the function
    mock_action.__name__ = "mock_action"

    task = BaseTask(name="task", action=mock_action)
    execution = BaseTaskExecution(task)

    result = await execution.run_default_action(ctx)
    assert result == "result"


@pytest.mark.asyncio
async def test_execute_successors():
    s1 = BaseTask(name="s1")
    s1.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", successor=[s1])
    execution = BaseTaskExecution(task)
    session = MagicMock(spec=AnySession)
    await execution.execute_successors(session)
    assert s1.exec_chain.called


@pytest.mark.asyncio
async def test_execute_fallbacks():
    f1 = BaseTask(name="f1")
    f1.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", fallback=[f1])
    execution = BaseTaskExecution(task)
    session = MagicMock(spec=AnySession)
    await execution.execute_fallbacks(session)
    assert f1.exec_chain.called


@pytest.mark.asyncio
async def test_execute_task_action_not_allowed():
    """Test execute_task_action returns early when not allowed to run."""
    task = BaseTask(name="test_task")
    execution = BaseTaskExecution(task)
    session = MagicMock(spec=AnySession)
    session.is_allowed_to_run.return_value = False

    ctx = MagicMock(spec=AnyContext)
    with patch.object(task, "get_ctx", return_value=ctx):
        result = await execution.execute_task_action(session)

    assert result is None
    ctx.log_info.assert_called_with("Not allowed to run")


@pytest.mark.asyncio
async def test_run_default_action_none():
    """Test run_default_action when action is None."""
    task = BaseTask(name="task")  # No action defined
    execution = BaseTaskExecution(task)
    ctx = MagicMock(spec=AnyContext)

    result = await execution.run_default_action(ctx)

    assert result is None
    ctx.log_debug.assert_called_with("No action defined for this task.")


@pytest.mark.asyncio
async def test_run_default_action_string_is_literal():
    """A bare string action is returned verbatim — never rendered."""
    task = BaseTask(name="task", action="literal {braces} string")
    execution = BaseTaskExecution(task)
    ctx = MagicMock(spec=AnyContext)

    result = await execution.run_default_action(ctx)

    assert result == "literal {braces} string"
    ctx.render.assert_not_called()


@pytest.mark.asyncio
async def test_run_default_action_tpl_is_rendered():
    """A `Tpl` action takes the callable branch and is rendered against ctx."""
    task = BaseTask(name="task", action=Tpl("{ctx.input.x}"))
    execution = BaseTaskExecution(task)
    ctx = MagicMock(spec=AnyContext)
    ctx.render.return_value = "rendered_value"

    result = await execution.run_default_action(ctx)

    assert result == "rendered_value"
    ctx.render.assert_called_once_with("{ctx.input.x}")


def test_skip_successors_marks_tasks_skipped():
    """Test skip_successors marks tasks as skipped."""
    s1 = BaseTask(name="s1")
    task = BaseTask(name="task", successor=[s1])
    execution = BaseTaskExecution(task)
    session = MagicMock(spec=AnySession)

    ctx = MagicMock(spec=AnyContext)
    status = MagicMock(spec=TaskStatus)
    status.is_skipped = False

    session.get_task_status.return_value = status
    with patch.object(task, "get_ctx", return_value=ctx):
        execution.skip_successors(session)

    status.mark_as_skipped.assert_called_once()


def test_skip_fallbacks_marks_tasks_skipped():
    """Test skip_fallbacks marks tasks as skipped."""
    f1 = BaseTask(name="f1")
    task = BaseTask(name="task", fallback=[f1])
    execution = BaseTaskExecution(task)
    session = MagicMock(spec=AnySession)

    ctx = MagicMock(spec=AnyContext)
    status = MagicMock(spec=TaskStatus)
    status.is_skipped = False

    session.get_task_status.return_value = status
    with patch.object(task, "get_ctx", return_value=ctx):
        execution.skip_fallbacks(session)

    status.mark_as_skipped.assert_called_once()


@pytest.mark.asyncio
async def test_execute_action_until_ready_with_readiness_checks():
    """Test execute_action_until_ready with readiness checks."""
    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", readiness_check=[check_task])
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    session.is_terminated = False

    ctx = MagicMock(spec=AnyContext)
    ctx.xcom = MagicMock()
    ctx.xcom.get.return_value = None

    check_status = MagicMock(spec=TaskStatus)
    check_status.is_completed = True
    check_status.is_failed = False

    task_status = MagicMock(spec=TaskStatus)
    task_status.is_completed = True
    task_status.is_failed = False
    task_status.is_permanently_failed = False

    def get_status(t):
        if t is check_task:
            return check_status
        return task_status

    session.get_task_status.side_effect = get_status

    # Use real asyncio.create_task and asyncio.gather — they properly await
    # coroutines, avoiding "never awaited" warnings from closed coroutines.
    mock_exec = AsyncMock(return_value="result")

    with patch.object(task, "get_ctx", return_value=ctx):
        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            with patch.object(execution, "execute_action_with_retry", new=mock_exec):
                result = await execution.execute_action_until_ready(session)

    assert result is None  # Returns None after deferring
    session.defer_action.assert_called()
    task_status.mark_as_ready.assert_called_once()


@pytest.mark.asyncio
async def test_readiness_marks_ready_despite_transient_attempt_failure():
    """Readiness completing between a failed attempt and its retry still marks ready.

    `is_failed` is per-attempt (cleared by the next mark_as_started); gating
    readiness on it silently dropped all downstream tasks whenever the checks
    finished mid-retry. Only a PERMANENT failure may block mark_as_ready.
    """
    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", readiness_check=[check_task])
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    session.is_terminated = False

    ctx = MagicMock(spec=AnyContext)
    ctx.xcom = MagicMock()
    ctx.xcom.get.return_value = None

    check_status = MagicMock(spec=TaskStatus)
    check_status.is_completed = True

    task_status = MagicMock(spec=TaskStatus)
    task_status.is_failed = True  # transient: attempt failed, retry pending
    task_status.is_permanently_failed = False

    def get_status(t):
        if t is check_task:
            return check_status
        return task_status

    session.get_task_status.side_effect = get_status

    with patch.object(task, "get_ctx", return_value=ctx):
        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            with patch.object(
                execution,
                "execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                await execution.execute_action_until_ready(session)

    task_status.mark_as_ready.assert_called_once()


@pytest.mark.asyncio
async def test_readiness_does_not_mark_ready_when_permanently_failed():
    """A permanently failed action blocks mark_as_ready even if checks pass."""
    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", readiness_check=[check_task])
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    session.is_terminated = False

    ctx = MagicMock(spec=AnyContext)
    ctx.xcom = MagicMock()
    ctx.xcom.get.return_value = None

    check_status = MagicMock(spec=TaskStatus)
    check_status.is_completed = True

    task_status = MagicMock(spec=TaskStatus)
    task_status.is_failed = True
    task_status.is_permanently_failed = True

    def get_status(t):
        if t is check_task:
            return check_status
        return task_status

    session.get_task_status.side_effect = get_status

    with patch.object(task, "get_ctx", return_value=ctx):
        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            with patch.object(
                execution,
                "execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                await execution.execute_action_until_ready(session)

    task_status.mark_as_ready.assert_not_called()


@pytest.mark.asyncio
async def test_readiness_check_exception_fails_task_instead_of_hanging():
    """A permanently failed readiness check fails the run instead of hanging.

    Logging and dropping the exception while the (possibly never-ending)
    action is still deferred leaves the whole run blocked in wait_deferred with
    no error exit.
    """
    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(side_effect=ValueError("port closed"))

    task = BaseTask(name="task", readiness_check=[check_task])
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    session.is_terminated = False

    ctx = MagicMock(spec=AnyContext)
    ctx.xcom = MagicMock()
    ctx.xcom.get.return_value = None

    check_status = MagicMock(spec=TaskStatus)
    task_status = MagicMock(spec=TaskStatus)
    task_status.is_permanently_failed = False
    task_status.is_completed = False

    def get_status(t):
        if t is check_task:
            return check_status
        return task_status

    session.get_task_status.side_effect = get_status

    with patch.object(task, "get_ctx", return_value=ctx):
        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            with patch.object(
                execution,
                "execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                with pytest.raises(ValueError, match="port closed"):
                    await execution.execute_action_until_ready(session)

    task_status.mark_as_permanently_failed.assert_called_once()
    session.defer_action.assert_not_called()
