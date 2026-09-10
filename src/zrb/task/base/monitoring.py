"""Readiness monitoring for `BaseTask`, kept alive after the task is ready.

Composed into `BaseTask` as `self._base_monitoring`. Holds a direct reference
to the sibling `BaseTaskExecution` part (constructed first, so it is
available at `BaseTaskMonitoring.__init__` time) to re-run the action when
readiness flips back to failing.
"""

import asyncio
from typing import TYPE_CHECKING

from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask
from zrb.util.run import gather_fail_fast, run_async
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    from zrb.task.base.base_task import BaseTask
    from zrb.task.base.execution import BaseTaskExecution


class BaseTaskMonitoring:
    """Re-checks readiness after a task is ready and re-runs its action on failure."""

    def __init__(self, task: "BaseTask", base_execution: "BaseTaskExecution") -> None:
        self._task = task
        self._base_execution = base_execution

    async def monitor_task_readiness(
        self, session: AnySession, action_coro: asyncio.Task
    ):
        """
        Monitors the readiness of a task after its initial execution.
        If readiness checks fail beyond a threshold, it cancels the original action,
        resets the task status, and re-executes the action.
        """
        task = self._task
        ctx = task.get_ctx(session)
        readiness_checks, check_period, fail_threshold, timeout = (
            self.get_readiness_config()
        )

        if not readiness_checks:
            ctx.log_debug("No readiness checks defined, monitoring is not applicable.")
            return

        failure_count = 0
        ctx.log_info("Starting readiness monitoring...")

        while not session.is_terminated:
            await asyncio.sleep(check_period)

            if session.is_terminated:
                break

            if failure_count < fail_threshold:
                ctx.log_info("Performing periodic readiness check...")
                await self._reset_check_tasks(session, readiness_checks, ctx)

                try:
                    all_ok = await self._run_readiness_checks(
                        session, readiness_checks, timeout
                    )
                    if all_ok:
                        ctx.log_info("Readiness check OK.")
                        failure_count = 0
                        continue
                    ctx.log_warning(
                        "Periodic readiness check failed (tasks did not complete)."
                    )
                    failure_count += 1
                except asyncio.TimeoutError:
                    failure_count += 1
                    ctx.log_warning(
                        f"Readiness check timed out ({timeout}s). "
                        f"Failure count: {failure_count}/{fail_threshold}"
                    )
                except (asyncio.CancelledError, KeyboardInterrupt):
                    ctx.log_info("Monitoring cancelled or interrupted.")
                    break
                except Exception as e:
                    failure_count += 1
                    ctx.log_error(
                        f"Readiness check failed with exception: {e}. "
                        f"Failure count: {failure_count}"
                    )

            if failure_count >= fail_threshold:
                ctx.log_warning(
                    f"Readiness failure threshold ({fail_threshold}) reached."
                )
                action_coro = await self._handle_threshold_reached(
                    session, action_coro, ctx
                )
                failure_count = 0
                ctx.log_info("Continuing monitoring...")

        ctx.log_info("Stopping readiness monitoring.")

    async def _reset_check_tasks(
        self, session: AnySession, readiness_checks: list[AnyTask], ctx
    ) -> None:
        """Reset status and XCom data for readiness check tasks."""
        for check in readiness_checks:
            session.get_task_status(check).reset_history()
            session.get_task_status(check).reset()
            check_xcom: Xcom | None = ctx.xcom.get(check.name)
            if check_xcom is not None:
                check_xcom.clear()

    async def _run_readiness_checks(
        self,
        session: AnySession,
        readiness_checks: list[AnyTask],
        readiness_timeout: float,
    ) -> bool:
        """Run all readiness checks and return True if all completed successfully."""
        readiness_check_coros = [
            run_async(check.exec_chain(session)) for check in readiness_checks
        ]
        try:
            # Fail-fast fan-out: a readiness check erroring should abort the wait
            # immediately, not be masked by return_exceptions.
            gather_coro = gather_fail_fast(*readiness_check_coros)
            if readiness_timeout > 0:
                await asyncio.wait_for(gather_coro, timeout=readiness_timeout)
            else:
                await gather_coro
            return all(
                session.get_task_status(check).is_completed
                for check in readiness_checks
            )
        except asyncio.TimeoutError:
            for check in readiness_checks:
                if not session.get_task_status(check).is_ready:
                    session.get_task_status(check).mark_as_failed()
            raise
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception:
            for check in readiness_checks:
                if not session.get_task_status(check).is_ready:
                    session.get_task_status(check).mark_as_failed()
            raise

    async def _handle_threshold_reached(
        self,
        session: AnySession,
        action_coro: asyncio.Task,
        ctx,
    ) -> asyncio.Task:
        """Cancel the current action, reset task, and re-execute. Returns the new action coroutine."""
        task = self._task
        if action_coro and not action_coro.done():
            ctx.log_info("Cancelling original task action...")
            action_coro.cancel()
            try:
                await action_coro
            except asyncio.CancelledError:
                # The action's cancellation is expected — we just requested it.
                # But if the MONITOR itself was cancelled while waiting, swallowing
                # here would make it uncancellable and restart the action after
                # shutdown. `cancelling()` distinguishes the two.
                current = asyncio.current_task()
                if current is not None and current.cancelling() > 0:
                    raise
            except Exception as e:
                # The action we just cancelled may surface its own error while
                # unwinding; it's already handled by the retry loop (logged and
                # marked failed there) — just make the swallow itself debuggable.
                ctx.log_debug(f"Cancelled action's own error handling: {e}")

        ctx.log_info("Resetting task status.")
        session.get_task_status(task).reset()

        ctx.log_info("Re-executing task action...")
        new_action_coro = asyncio.create_task(
            run_async(self._base_execution.execute_action_with_retry(session))
        )
        session.defer_action(task, new_action_coro)
        return new_action_coro

    def get_readiness_config(self) -> tuple[list[AnyTask], float, int, float]:
        """Extract readiness check parameters from task, falling back to defaults."""
        task = self._task
        checks = task.readiness_checks
        return (
            checks,
            task.readiness_check_period,
            task.readiness_failure_threshold,
            task.readiness_timeout,
        )
