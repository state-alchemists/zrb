import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.session.any_session import AnySession
from zrb.task.base.base_task import BaseTask
from zrb.task.base.execution import BaseTaskExecution
from zrb.task_status.task_status import TaskStatus


@pytest.mark.asyncio
async def test_readiness_check_exception_fails_fast_beside_a_polling_check():
    """One failing check fails the task even when a sibling never returns.

    Regression: gathering the checks with return_exceptions=True waited for all
    of them. Readiness checks poll until they succeed (HttpCheck/TcpCheck never
    return on their own), so the failure never surfaced and the run hung — the
    exact hazard the fail-fast path below exists to avoid. The polling sibling
    must be cancelled instead.
    """
    never = asyncio.Event()
    polling_cancelled = asyncio.Event()

    async def poll_forever(_session):
        try:
            await never.wait()
        except asyncio.CancelledError:
            polling_cancelled.set()
            raise

    failing_check = BaseTask(name="failing_check")
    failing_check.exec_chain = AsyncMock(side_effect=ValueError("port closed"))
    polling_check = BaseTask(name="polling_check")
    polling_check.exec_chain = poll_forever

    task = BaseTask(
        name="task",
        readiness_check=[failing_check, polling_check],
        readiness_check_delay=0,
    )
    execution = BaseTaskExecution(task)

    session = MagicMock(spec=AnySession)
    session.is_terminated = False

    ctx = MagicMock(spec=AnyContext)
    ctx.xcom = MagicMock()
    ctx.xcom.get.return_value = None

    task_status = MagicMock(spec=TaskStatus)
    task_status.is_permanently_failed = False
    task_status.is_completed = False
    session.get_task_status.side_effect = lambda t: (
        task_status if t is task else MagicMock(spec=TaskStatus)
    )

    with patch.object(task, "get_ctx", return_value=ctx):
        with patch.object(
            execution,
            "execute_action_with_retry",
            new=AsyncMock(return_value="result"),
        ):
            with pytest.raises(ValueError, match="port closed"):
                await asyncio.wait_for(
                    execution.execute_action_until_ready(session), timeout=5
                )

    assert polling_cancelled.is_set()
    session.defer_action.assert_not_called()


@pytest.mark.asyncio
async def test_incomplete_readiness_check_fails_task_instead_of_hanging():
    """Readiness checks that finish without completing also fail the run."""
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
            with patch.object(
                execution,
                "execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                with pytest.raises(RuntimeError, match="did not complete"):
                    await execution.execute_action_until_ready(session)

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

    mock_skip_successors = MagicMock()
    mock_execute_fallbacks = AsyncMock()
    with patch.object(task, "get_ctx", return_value=ctx):
        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            with patch.object(
                execution,
                "execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                with patch.object(
                    execution, "skip_successors", new=mock_skip_successors
                ):
                    with patch.object(
                        execution, "execute_fallbacks", new=mock_execute_fallbacks
                    ):
                        with pytest.raises(ValueError, match="port closed"):
                            await execution.execute_action_until_ready(session)

    task_status.mark_as_permanently_failed.assert_called_once()
    mock_skip_successors.assert_called_once_with(session)
    mock_execute_fallbacks.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_readiness_failure_surfaces_action_error_without_rerunning_fallbacks():
    """When the action itself crashed, its error is the root cause.

    The retry loop's terminal path already marked the task permanently failed
    and ran the fallbacks — the readiness fail-fast path must not run them a
    second time, and must raise the action's exception (not the readiness
    symptom).
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
            with patch.object(
                execution,
                "execute_action_with_retry",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ):
                with patch.object(
                    execution, "execute_fallbacks", new=mock_execute_fallbacks
                ):
                    with pytest.raises(RuntimeError, match="boom"):
                        await execution.execute_action_until_ready(session)

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
            with patch.object(
                execution,
                "execute_action_with_retry",
                new=AsyncMock(return_value="result"),
            ):
                with patch.object(
                    execution, "skip_successors", new=mock_skip_successors
                ):
                    with patch.object(
                        execution, "execute_fallbacks", new=mock_execute_fallbacks
                    ):
                        with pytest.raises(ValueError, match="port closed"):
                            await execution.execute_action_until_ready(session)

    task_status.mark_as_permanently_failed.assert_not_called()
    mock_skip_successors.assert_not_called()
    mock_execute_fallbacks.assert_not_awaited()


@pytest.mark.asyncio
async def test_diamond_upstreams_run_readiness_task_once():
    """Two upstreams completing in the same tick must not double-run the task.

    `is_started` must be set before the readiness path's first suspension
    point. Set it only inside the created action task and both upstream chains
    pass `is_allowed_to_run`, running the action twice concurrently.
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
