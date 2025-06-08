import asyncio
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import AnyContext
from zrb.session.any_session import AnySession
from zrb.util.attr import get_bool_attr
from zrb.util.run import run_async
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    from zrb.task.base_task import BaseTask


async def execute_task_chain(task: "BaseTask", session: AnySession):
    """
    Executes the task and its downstream successors if conditions are met.
    """
    if session.is_terminated or not session.is_allowed_to_run(task):
        return
    result = await execute_task_action(task, session)
    # Get next tasks
    nexts = session.get_next_tasks(task)
    if session.is_terminated or len(nexts) == 0:
        return result
    # Run next tasks asynchronously
    next_coros = [run_async(next_task.exec_chain(session)) for next_task in nexts]
    # Wait for the next tasks to complete. The result of the current task is returned.
    await asyncio.gather(*next_coros)
    return result


async def execute_task_action(task: "BaseTask", session: AnySession):
    """
    Executes a single task's action, handling conditions and readiness checks.
    """
    ctx = task.get_ctx(session)
    if not session.is_allowed_to_run(task):
        # Task is not allowed to run, skip it for now.
        # This will be triggered later if dependencies are met.
        ctx.log_info("Not allowed to run")
        return
    if not check_execute_condition(task, session):
        # Skip the task based on its execute_condition
        ctx.log_info("Marked as skipped (condition false)")
        session.get_task_status(task).mark_as_skipped()
        return
    # Wait for task to be ready (handles action execution, readiness checks)
    return await run_async(execute_action_until_ready(task, session))


def check_execute_condition(task: "BaseTask", session: AnySession) -> bool:
    """
    Evaluates the task's execute_condition attribute.
    """
    ctx = task.get_ctx(session)
    execute_condition_attr = getattr(task, "_execute_condition", True)
    return get_bool_attr(ctx, execute_condition_attr, True, auto_render=True)


async def execute_action_until_ready(task: "BaseTask", session: AnySession):
    """
    Manages the execution of the task's action, coordinating with readiness checks.
    """
    ctx = task.get_ctx(session)
    readiness_checks = task.readiness_checks
    readiness_check_delay = getattr(task, "_readiness_check_delay", 0.5)
    monitor_readiness = getattr(task, "_monitor_readiness", False)

    if not readiness_checks:  # Simplified check for empty list
        ctx.log_info("No readiness checks")
        # Task has no readiness check, execute action directly
        result = await run_async(execute_action_with_retry(task, session))
        # Mark ready only if the action completed successfully (not failed/cancelled)
        if session.get_task_status(task).is_completed:
            ctx.log_info("Marked as ready")
            session.get_task_status(task).mark_as_ready()
        return result

    # Start the task action and readiness checks concurrently
    ctx.log_info("Starting action and readiness checks")
    action_coro = asyncio.create_task(
        run_async(execute_action_with_retry(task, session))
    )

    await asyncio.sleep(readiness_check_delay)

    readiness_check_coros = [
        run_async(check.exec_chain(session)) for check in readiness_checks
    ]

    # Wait primarily for readiness checks to complete
    ctx.log_info("Waiting for readiness checks")
    readiness_passed = False
    try:
        # Gather results, but primarily interested in completion/errors
        await asyncio.gather(*readiness_check_coros)
        # Check if all readiness tasks actually completed successfully
        all_readiness_completed = all(
            session.get_task_status(check).is_completed for check in readiness_checks
        )
        if all_readiness_completed:
            ctx.log_info("Readiness checks completed successfully")
            readiness_passed = True
            # Mark task as ready only if checks passed and action didn't fail during checks
            if not session.get_task_status(task).is_failed:
                ctx.log_info("Marked as ready")
                session.get_task_status(task).mark_as_ready()
        else:
            ctx.log_warning(
                "One or more readiness checks did not complete successfully."
            )

    except Exception as e:
        ctx.log_error(f"Readiness check failed with exception: {e}")
        # If readiness checks fail with an exception, the task is not ready.
        # The action_coro might still be running or have failed.
        # execute_action_with_retry handles marking the main task status.

    # Defer the main action coroutine; it will be awaited later if needed
    session.defer_action(task, action_coro)

    # Start monitoring only if readiness passed and monitoring is enabled
    if readiness_passed and monitor_readiness:
        # Import dynamically to avoid circular dependency if monitoring imports execution
        from zrb.task.base.monitoring import monitor_task_readiness

        monitor_coro = asyncio.create_task(
            run_async(monitor_task_readiness(task, session, action_coro))
        )
        session.defer_monitoring(task, monitor_coro)

    # The result here is primarily about readiness check completion.
    # The actual task result is handled by the deferred action_coro.
    return None


async def execute_action_with_retry(task: "BaseTask", session: AnySession) -> Any:
    """
    Executes the task's core action (`_exec_action`) with retry logic,
    handling success (triggering successors) and failure (triggering fallbacks).
    """
    ctx = task.get_ctx(session)
    retries = getattr(task, "_retries", 2)
    retry_period = getattr(task, "_retry_period", 0)
    max_attempt = retries + 1
    ctx.set_max_attempt(max_attempt)

    for attempt in range(max_attempt):
        ctx.set_attempt(attempt + 1)
        if attempt > 0:
            ctx.log_info(f"Retrying in {retry_period}s...")
            await asyncio.sleep(retry_period)

        try:
            ctx.log_info("Marked as started")
            session.get_task_status(task).mark_as_started()

            # Execute the underlying action (which might be overridden in subclasses)
            # We call the task's _exec_action method directly here.
            result = await run_async(task._exec_action(ctx))

            ctx.log_info("Marked as completed")
            session.get_task_status(task).mark_as_completed()

            # Store result in XCom
            task_xcom: Xcom = ctx.xcom.get(task.name)
            task_xcom.push(result)

            # Skip fallbacks and execute successors on success
            skip_fallbacks(task, session)
            await run_async(execute_successors(task, session))
            return result

        except (asyncio.CancelledError, KeyboardInterrupt):
            ctx.log_warning("Task cancelled or interrupted")
            session.get_task_status(task).mark_as_failed()  # Mark as failed on cancel
            # Do not trigger fallbacks/successors on cancellation
            raise
        except BaseException as e:
            ctx.log_error(f"Attempt {attempt + 1}/{max_attempt} failed: {e}")
            session.get_task_status(
                task
            ).mark_as_failed()  # Mark failed for this attempt

            if attempt < max_attempt - 1:
                # More retries available
                continue
            else:
                # Final attempt failed
                ctx.log_error("Marked as permanently failed")
                session.get_task_status(task).mark_as_permanently_failed()
                # Skip successors and execute fallbacks on permanent failure
                skip_successors(task, session)
                await run_async(execute_fallbacks(task, session))
                raise e  # Re-raise the exception after handling fallbacks


async def run_default_action(task: "BaseTask", ctx: AnyContext) -> Any:
    """
    Executes the specific action defined by the '_action' attribute for BaseTask.
    This is the default implementation called by BaseTask._exec_action.
    Subclasses like LLMTask override _exec_action with their own logic.
    """
    action = getattr(task, "_action", None)
    if action is None:
        ctx.log_debug("No action defined for this task.")
        return None
    if isinstance(action, str):
        # Render f-string action
        rendered_action = ctx.render(action)
        ctx.log_debug(f"Rendered action string: {rendered_action}")
        # Assuming string actions are meant to be returned as is.
        # If they need execution (e.g., shell commands), that logic would go here.
        return rendered_action
    elif callable(action):
        # Execute callable action
        ctx.log_debug(f"Executing callable action: {action.__name__}")
        return await run_async(action(ctx))
    else:
        ctx.log_warning(f"Unsupported action type: {type(action)}")
        return None


async def execute_successors(task: "BaseTask", session: "AnySession"):
    """Executes all successor tasks."""
    ctx = task.get_ctx(session)
    successors = task.successors
    if successors:
        ctx.log_info(f"Executing {len(successors)} successor(s)")
        successor_coros = [
            run_async(successor.exec_chain(session)) for successor in successors
        ]
        await asyncio.gather(*successor_coros)
    else:
        ctx.log_debug("No successors to execute.")


def skip_successors(task: "BaseTask", session: AnySession):
    """Marks all successor tasks as skipped."""
    ctx = task.get_ctx(session)
    successors = task.successors
    if successors:
        ctx.log_info(f"Skipping {len(successors)} successor(s)")
        for successor in successors:
            # Check if already skipped to avoid redundant logging/state changes
            if not session.get_task_status(successor).is_skipped:
                session.get_task_status(successor).mark_as_skipped()


async def execute_fallbacks(task: "BaseTask", session: AnySession):
    """Executes all fallback tasks."""
    ctx = task.get_ctx(session)
    fallbacks = task.fallbacks
    if fallbacks:
        ctx.log_info(f"Executing {len(fallbacks)} fallback(s)")
        fallback_coros = [
            run_async(fallback.exec_chain(session)) for fallback in fallbacks
        ]
        await asyncio.gather(*fallback_coros)
    else:
        ctx.log_debug("No fallbacks to execute.")


def skip_fallbacks(task: "BaseTask", session: AnySession):
    """Marks all fallback tasks as skipped."""
    ctx = task.get_ctx(session)
    fallbacks = task.fallbacks
    if fallbacks:
        ctx.log_info(f"Skipping {len(fallbacks)} fallback(s)")
        for fallback in fallbacks:
            # Check if already skipped
            if not session.get_task_status(fallback).is_skipped:
                session.get_task_status(fallback).mark_as_skipped()
