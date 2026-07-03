import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

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
    session = MagicMock(spec=AnySession)
    session.is_terminated = False
    session.is_allowed_to_run.return_value = False

    result = await execute_task_chain(task, session)
    assert result is None
    session.get_next_tasks.assert_not_called()


@pytest.mark.asyncio
async def test_execute_task_chain_success():
    task = BaseTask(name="test_task")
    session = MagicMock(spec=AnySession)
    session.is_terminated = False
    session.is_allowed_to_run.return_value = True

    mock_execute_task_action = AsyncMock(return_value="success")

    with patch(
        "zrb.task.base.execution.execute_task_action",
        new=mock_execute_task_action,
    ):
        next_task = BaseTask(name="next_task")
        next_task.exec_chain = AsyncMock(return_value=None)

        session.get_next_tasks.return_value = [next_task]

        result = await execute_task_chain(task, session)

        assert result == "success"
        assert next_task.exec_chain.called


@pytest.mark.asyncio
async def test_execute_task_action_condition_false():
    task = BaseTask(name="test_task", execute_condition=False)

    session = MagicMock(spec=AnySession)
    session.is_allowed_to_run.return_value = True
    status = MagicMock(spec=TaskStatus)
    session.get_task_status.return_value = status

    with patch("zrb.task.base.execution.get_bool_attr", return_value=False):
        await execute_task_action(task, session)
        assert status.mark_as_skipped.called


@pytest.mark.asyncio
async def test_execute_action_until_ready_no_checks():
    task = BaseTask(name="test_task")
    session = MagicMock(spec=AnySession)
    status = MagicMock(spec=TaskStatus)
    status.is_completed = True
    session.get_task_status.return_value = status

    with patch(
        "zrb.task.base.execution.execute_action_with_retry",
        new=AsyncMock(return_value="done"),
    ):
        result = await execute_action_until_ready(task, session)

        assert result == "done"
        assert status.mark_as_ready.called


@pytest.mark.asyncio
async def test_execute_action_with_retry_success():

    async def mock_action(ctx):
        return "ok"

    # Set __name__ attribute on the function
    mock_action.__name__ = "mock_action"

    task = BaseTask(name="task", retries=1, retry_period=0, action=mock_action)

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

    session = MagicMock(spec=AnySession)
    status = MagicMock(spec=TaskStatus)
    session.get_task_status.return_value = status

    ctx = MagicMock(spec=AnyContext)
    with patch.object(task, "get_ctx", return_value=ctx):
        with pytest.raises(Exception, match="boom"):
            await execute_action_with_retry(task, session)

        assert status.mark_as_failed.called
        assert status.mark_as_permanently_failed.called


@pytest.mark.asyncio
async def test_run_default_action_callable():
    ctx = MagicMock(spec=AnyContext)

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
    s1.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", successor=[s1])
    session = MagicMock(spec=AnySession)
    await execute_successors(task, session)
    assert s1.exec_chain.called


@pytest.mark.asyncio
async def test_execute_fallbacks():
    f1 = BaseTask(name="f1")
    f1.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", fallback=[f1])
    session = MagicMock(spec=AnySession)
    await execute_fallbacks(task, session)
    assert f1.exec_chain.called


@pytest.mark.asyncio
async def test_execute_task_action_not_allowed():
    """Test execute_task_action returns early when not allowed to run."""
    from zrb.task.base.execution import execute_task_action

    task = BaseTask(name="test_task")
    session = MagicMock(spec=AnySession)
    session.is_allowed_to_run.return_value = False

    ctx = MagicMock(spec=AnyContext)
    with patch.object(task, "get_ctx", return_value=ctx):
        result = await execute_task_action(task, session)

    assert result is None
    ctx.log_info.assert_called_with("Not allowed to run")


@pytest.mark.asyncio
async def test_run_default_action_none():
    """Test run_default_action when action is None."""
    from zrb.task.base.execution import run_default_action

    task = BaseTask(name="task")  # No action defined
    ctx = MagicMock(spec=AnyContext)

    result = await run_default_action(task, ctx)

    assert result is None
    ctx.log_debug.assert_called_with("No action defined for this task.")


@pytest.mark.asyncio
async def test_run_default_action_string():
    """Test run_default_action with string action."""
    from zrb.task.base.execution import run_default_action

    task = BaseTask(name="task", action="rendered_string")
    ctx = MagicMock(spec=AnyContext)
    ctx.render.return_value = "rendered_value"

    result = await run_default_action(task, ctx)

    assert result == "rendered_value"


def test_skip_successors_marks_tasks_skipped():
    """Test skip_successors marks tasks as skipped."""
    from zrb.task.base.execution import skip_successors

    s1 = BaseTask(name="s1")
    task = BaseTask(name="task", successor=[s1])
    session = MagicMock(spec=AnySession)

    ctx = MagicMock(spec=AnyContext)
    status = MagicMock(spec=TaskStatus)
    status.is_skipped = False

    session.get_task_status.return_value = status
    with patch.object(task, "get_ctx", return_value=ctx):
        skip_successors(task, session)

    status.mark_as_skipped.assert_called_once()


def test_skip_fallbacks_marks_tasks_skipped():
    """Test skip_fallbacks marks tasks as skipped."""
    from zrb.task.base.execution import skip_fallbacks

    f1 = BaseTask(name="f1")
    task = BaseTask(name="task", fallback=[f1])
    session = MagicMock(spec=AnySession)

    ctx = MagicMock(spec=AnyContext)
    status = MagicMock(spec=TaskStatus)
    status.is_skipped = False

    session.get_task_status.return_value = status
    with patch.object(task, "get_ctx", return_value=ctx):
        skip_fallbacks(task, session)

    status.mark_as_skipped.assert_called_once()


@pytest.mark.asyncio
async def test_execute_action_until_ready_with_readiness_checks():
    """Test execute_action_until_ready with readiness checks."""
    from zrb.task.base.execution import execute_action_until_ready

    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", readiness_check=[check_task])

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
            with patch(
                "zrb.task.base.execution.execute_action_with_retry",
                new=mock_exec,
            ):
                result = await execute_action_until_ready(task, session)

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
    from zrb.task.base.execution import execute_action_until_ready

    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", readiness_check=[check_task])

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
            with patch(
                "zrb.task.base.execution.execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                await execute_action_until_ready(task, session)

    task_status.mark_as_ready.assert_called_once()


@pytest.mark.asyncio
async def test_readiness_does_not_mark_ready_when_permanently_failed():
    """A permanently failed action blocks mark_as_ready even if checks pass."""
    from zrb.task.base.execution import execute_action_until_ready

    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", readiness_check=[check_task])

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
            with patch(
                "zrb.task.base.execution.execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                await execute_action_until_ready(task, session)

    task_status.mark_as_ready.assert_not_called()


@pytest.mark.asyncio
async def test_readiness_check_exception_fails_task_instead_of_hanging():
    """A permanently failed readiness check fails the run instead of hanging.

    The exception used to be logged and dropped while the (possibly
    never-ending) action was still deferred, leaving the whole run blocked in
    wait_deferred with no error exit.
    """
    from zrb.task.base.execution import execute_action_until_ready

    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(side_effect=ValueError("port closed"))

    task = BaseTask(name="task", readiness_check=[check_task])

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
            with patch(
                "zrb.task.base.execution.execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                with pytest.raises(ValueError, match="port closed"):
                    await execute_action_until_ready(task, session)

    task_status.mark_as_permanently_failed.assert_called_once()
    session.defer_action.assert_not_called()


@pytest.mark.asyncio
async def test_incomplete_readiness_check_fails_task_instead_of_hanging():
    """Readiness checks that finish without completing also fail the run."""
    from zrb.task.base.execution import execute_action_until_ready

    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(return_value=None)

    task = BaseTask(name="task", readiness_check=[check_task])

    session = MagicMock(spec=AnySession)
    session.is_terminated = False

    ctx = MagicMock(spec=AnyContext)
    ctx.xcom = MagicMock()
    ctx.xcom.get.return_value = None

    check_status = MagicMock(spec=TaskStatus)
    check_status.is_completed = False  # e.g. skipped/terminated, never completed

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
            with patch(
                "zrb.task.base.execution.execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                with pytest.raises(RuntimeError, match="did not complete"):
                    await execute_action_until_ready(task, session)

    task_status.mark_as_permanently_failed.assert_called_once()
    session.defer_action.assert_not_called()


@pytest.mark.asyncio
async def test_readiness_failure_runs_fallbacks_and_skips_successors():
    """Readiness failure is a permanent failure — fallbacks must fire.

    The retry loop pairs mark_as_permanently_failed with skip_successors +
    execute_fallbacks; the readiness fail-fast path must do the same, or a
    `fallback=` on a server task silently never runs when the readiness check
    (rather than the action) is what dies.
    """
    from zrb.task.base.execution import execute_action_until_ready

    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(side_effect=ValueError("port closed"))

    task = BaseTask(name="task", readiness_check=[check_task])

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

    mock_skip_successors = MagicMock()
    mock_execute_fallbacks = AsyncMock()
    with patch.object(task, "get_ctx", return_value=ctx):
        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            with patch(
                "zrb.task.base.execution.execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                with patch(
                    "zrb.task.base.execution.skip_successors",
                    new=mock_skip_successors,
                ):
                    with patch(
                        "zrb.task.base.execution.execute_fallbacks",
                        new=mock_execute_fallbacks,
                    ):
                        with pytest.raises(ValueError, match="port closed"):
                            await execute_action_until_ready(task, session)

    task_status.mark_as_permanently_failed.assert_called_once()
    mock_skip_successors.assert_called_once_with(task, session)
    mock_execute_fallbacks.assert_awaited_once_with(task, session)


@pytest.mark.asyncio
async def test_readiness_failure_surfaces_action_error_without_rerunning_fallbacks():
    """When the action itself crashed, its error is the root cause.

    The retry loop's terminal path already marked the task permanently failed
    and ran the fallbacks — the readiness fail-fast path must not run them a
    second time, and must raise the action's exception (not the readiness
    symptom).
    """
    from zrb.task.base.execution import execute_action_until_ready

    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(side_effect=ValueError("port closed"))

    task = BaseTask(name="task", readiness_check=[check_task])

    session = MagicMock(spec=AnySession)
    session.is_terminated = False

    ctx = MagicMock(spec=AnyContext)
    ctx.xcom = MagicMock()
    ctx.xcom.get.return_value = None

    check_status = MagicMock(spec=TaskStatus)
    task_status = MagicMock(spec=TaskStatus)
    # The action's retry loop already did the terminal bookkeeping.
    task_status.is_permanently_failed = True

    def get_status(t):
        if t is check_task:
            return check_status
        return task_status

    session.get_task_status.side_effect = get_status

    mock_execute_fallbacks = AsyncMock()
    with patch.object(task, "get_ctx", return_value=ctx):
        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            with patch(
                "zrb.task.base.execution.execute_action_with_retry",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ):
                with patch(
                    "zrb.task.base.execution.execute_fallbacks",
                    new=mock_execute_fallbacks,
                ):
                    with pytest.raises(RuntimeError, match="boom"):
                        await execute_action_until_ready(task, session)

    task_status.mark_as_permanently_failed.assert_not_called()
    mock_execute_fallbacks.assert_not_awaited()


@pytest.mark.asyncio
async def test_readiness_failure_after_completed_action_does_not_run_fallbacks():
    """A completed action already ran its successors and skipped its fallbacks.

    When readiness then fails (short action + broken check), stacking
    mark_as_permanently_failed on a completed task and firing fallbacks AFTER
    the successors would be contradictory. The readiness error still
    propagates so the run fails visibly.
    """
    from zrb.task.base.execution import execute_action_until_ready

    check_task = BaseTask(name="check_task")
    check_task.exec_chain = AsyncMock(side_effect=ValueError("port closed"))

    task = BaseTask(name="task", readiness_check=[check_task])

    session = MagicMock(spec=AnySession)
    session.is_terminated = False

    ctx = MagicMock(spec=AnyContext)
    ctx.xcom = MagicMock()
    ctx.xcom.get.return_value = None

    check_status = MagicMock(spec=TaskStatus)
    task_status = MagicMock(spec=TaskStatus)
    task_status.is_permanently_failed = False
    # The action finished successfully before readiness resolved.
    task_status.is_completed = True

    def get_status(t):
        if t is check_task:
            return check_status
        return task_status

    session.get_task_status.side_effect = get_status

    mock_skip_successors = MagicMock()
    mock_execute_fallbacks = AsyncMock()
    with patch.object(task, "get_ctx", return_value=ctx):
        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            with patch(
                "zrb.task.base.execution.execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                with patch(
                    "zrb.task.base.execution.skip_successors",
                    new=mock_skip_successors,
                ):
                    with patch(
                        "zrb.task.base.execution.execute_fallbacks",
                        new=mock_execute_fallbacks,
                    ):
                        with pytest.raises(ValueError, match="port closed"):
                            await execute_action_until_ready(task, session)

    task_status.mark_as_permanently_failed.assert_not_called()
    mock_skip_successors.assert_not_called()
    mock_execute_fallbacks.assert_not_awaited()


@pytest.mark.asyncio
async def test_diamond_upstreams_run_readiness_task_once():
    """Two upstreams completing in the same tick must not double-run the task.

    `is_started` used to be set only inside the created action task — after
    the readiness path's first suspension point — so both upstream chains
    passed `is_allowed_to_run` and the action executed twice concurrently.
    """
    executions = []

    check = BaseTask(name="check", action=lambda ctx: "ok")
    a = BaseTask(name="a", action=lambda ctx: "a")
    b = BaseTask(name="b", action=lambda ctx: "b")
    d = BaseTask(
        name="d",
        action=lambda ctx: executions.append("d"),
        upstream=[a, b],
        readiness_check=[check],
        readiness_check_delay=0,
    )

    await d.async_run()

    assert executions == ["d"]
