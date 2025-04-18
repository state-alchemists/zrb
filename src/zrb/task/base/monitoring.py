import asyncio

from zrb.session.any_session import AnySession
from zrb.task.base.execution import execute_action_with_retry
from zrb.task.base_task import BaseTask
from zrb.util.run import run_async
from zrb.xcom.xcom import Xcom


async def monitor_task_readiness(
    task: BaseTask, session: AnySession, action_coro: asyncio.Task
):
    """
    Monitors the readiness of a task after its initial execution.
    If readiness checks fail beyond a threshold, it cancels the original action,
    resets the task status, and re-executes the action.
    """
    ctx = task.get_ctx(session)
    readiness_checks = task.readiness_checks
    readiness_check_period = getattr(task, "_readiness_check_period", 5.0)
    readiness_failure_threshold = getattr(task, "_readiness_failure_threshold", 1)
    readiness_timeout = getattr(task, "_readiness_timeout", 60)

    if not readiness_checks:
        ctx.log_debug("No readiness checks defined, monitoring is not applicable.")
        return

    failure_count = 0
    ctx.log_info("Starting readiness monitoring...")

    while not session.is_terminated:
        await asyncio.sleep(readiness_check_period)

        if session.is_terminated:
            break  # Exit loop if session terminated during sleep

        if failure_count < readiness_failure_threshold:
            ctx.log_info("Performing periodic readiness check...")
            # Reset status and XCom for readiness check tasks before re-running
            for check in readiness_checks:
                session.get_task_status(check).reset_history()
                session.get_task_status(check).reset()
                # Clear previous XCom data for the check task if needed
                check_xcom: Xcom = ctx.xcom.get(check.name)
                check_xcom.clear()

            readiness_check_coros = [
                run_async(check.exec_chain(session)) for check in readiness_checks
            ]

            try:
                # Wait for checks with a timeout
                await asyncio.wait_for(
                    asyncio.gather(*readiness_check_coros),
                    timeout=readiness_timeout,
                )
                # Check if all checks actually completed successfully
                all_checks_completed = all(
                    session.get_task_status(check).is_completed
                    for check in readiness_checks
                )
                if all_checks_completed:
                    ctx.log_info("Readiness check OK.")
                    failure_count = 0  # Reset failure count on success
                    continue  # Continue monitoring
                else:
                    ctx.log_warning(
                        "Periodic readiness check failed (tasks did not complete)."
                    )
                    failure_count += 1

            except asyncio.TimeoutError:
                failure_count += 1
                ctx.log_warning(
                    f"Readiness check timed out ({readiness_timeout}s). "
                    f"Failure count: {failure_count}/{readiness_failure_threshold}"
                )
                # Ensure check tasks are marked as failed on timeout
                for check in readiness_checks:
                    if not session.get_task_status(check).is_finished:
                        session.get_task_status(check).mark_as_failed()

            except (asyncio.CancelledError, KeyboardInterrupt):
                ctx.log_info("Monitoring cancelled or interrupted.")
                break  # Exit monitoring loop

            except Exception as e:
                failure_count += 1
                ctx.log_error(
                    f"Readiness check failed with exception: {e}. "
                    f"Failure count: {failure_count}"
                )
                # Mark checks as failed
                for check in readiness_checks:
                    if not session.get_task_status(check).is_finished:
                        session.get_task_status(check).mark_as_failed()

        # If failure threshold is reached
        if failure_count >= readiness_failure_threshold:
            ctx.log_warning(
                f"Readiness failure threshold ({readiness_failure_threshold}) reached."
            )

            # Cancel the original running action if it's still running
            if action_coro and not action_coro.done():
                ctx.log_info("Cancelling original task action...")
                action_coro.cancel()
                try:
                    await action_coro  # Allow cancellation to process
                except asyncio.CancelledError:
                    ctx.log_info("Original task action cancelled.")
                except Exception as e:
                    ctx.log_warning(f"Error during original action cancellation: {e}")

            # Reset the main task status
            ctx.log_info("Resetting task status.")
            session.get_task_status(task).reset()

            # Re-execute the action (with retries)
            ctx.log_info("Re-executing task action...")
            # Import dynamically to avoid circular dependency
            new_action_coro = asyncio.create_task(
                run_async(execute_action_with_retry(task, session))
            )
            # Defer the new action coroutine
            session.defer_action(task, new_action_coro)
            # Update the reference for the next monitoring cycle
            action_coro = new_action_coro

            # Reset failure count after attempting restart
            failure_count = 0
            ctx.log_info("Continuing monitoring...")

    ctx.log_info("Stopping readiness monitoring.")
