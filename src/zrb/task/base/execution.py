import asyncio
import traceback
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext, current_ctx
from zrb.session.any_session import AnySession
from zrb.util.attr import get_bool_attr
from zrb.util.run import gather_isolated, run_async
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
    await gather_isolated(*next_coros)
    return result


async def execute_task_action(task: "BaseTask", session: AnySession):
    """
    Executes a single task's action, handling conditions and readiness checks.
    """
    ctx = task.get_ctx(session)
    token = current_ctx.set(ctx)
    try:
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
    finally:
        current_ctx.reset(token)


def check_execute_condition(task: "BaseTask", session: AnySession) -> bool:
    """
    Evaluates the task's execute_condition attribute.
    """
    ctx = task.get_ctx(session)
    execute_condition_attr = (
        task.execute_condition if task.execute_condition is not None else True
    )
    return get_bool_attr(ctx, execute_condition_attr, True, auto_render=True)


async def execute_action_until_ready(task: "BaseTask", session: AnySession):
    """
    Manages the execution of the task's action, coordinating with readiness checks.
    """
    ctx = task.get_ctx(session)
    readiness_checks = task.readiness_checks
    readiness_check_delay = (
        task.readiness_check_delay
        if task.readiness_check_delay is not None
        else CFG.TASK_READINESS_DELAY / 1000
    )
    monitor_readiness = bool(task.monitor_readiness)

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
    # Mark started BEFORE the first suspension point. `is_allowed_to_run` gates
    # on `is_started`, which is otherwise only set inside the created task —
    # after this coroutine yields at the sleep below. Two upstreams completing
    # in the same event-loop tick would then both pass the gate and run the
    # action twice (the second defer_action also overwrites the first, leaving
    # an orphaned task). The retry loop calls mark_as_started per attempt
    # anyway, so the early call is idempotent.
    session.get_task_status(task).mark_as_started()
    action_coro = asyncio.create_task(
        run_async(execute_action_with_retry(task, session))
    )

    try:
        await asyncio.sleep(readiness_check_delay)

        readiness_check_coros = [
            run_async(check.exec_chain(session)) for check in readiness_checks
        ]

        # Wait primarily for readiness checks to complete
        ctx.log_info("Waiting for readiness checks")
        readiness_passed = False
        readiness_error: BaseException | None = None
        readiness_timeout = CFG.TASK_READINESS_TIMEOUT / 1000
        try:
            # return_exceptions isolates the fan-out: one failing check no longer
            # orphans its siblings mid-flight (we inspect statuses/results below).
            gather_coro = asyncio.gather(*readiness_check_coros, return_exceptions=True)
            # Optional aggregate cap (CFG.TASK_READINESS_TIMEOUT; 0 = off). Without
            # it, a check that hangs and never returns hangs the whole run here.
            if readiness_timeout > 0:
                results = await asyncio.wait_for(gather_coro, timeout=readiness_timeout)
            else:
                results = await gather_coro
            # A check that raised is a hard readiness failure — surface it and
            # skip the completion check (matches the pre-isolation behavior,
            # where the raising gather jumped straight to the except branch).
            check_errors = [r for r in results if isinstance(r, Exception)]
            if check_errors:
                readiness_error = check_errors[0]
                ctx.log_error(
                    f"Readiness check failed with exception: {readiness_error}"
                )
            all_readiness_completed = not check_errors and all(
                session.get_task_status(check).is_completed
                for check in readiness_checks
            )
            if all_readiness_completed:
                ctx.log_info("Readiness checks completed successfully")
                readiness_passed = True
                # Gate on PERMANENT failure only. `is_failed` is transient — set
                # on every failed attempt and cleared by the next attempt's
                # mark_as_started — so checking it here races with the retry
                # loop: readiness completing between a failed attempt and its
                # retry would skip mark_as_ready forever (nothing re-evaluates
                # readiness), silently dropping all downstream tasks.
                if not session.get_task_status(task).is_permanently_failed:
                    ctx.log_info("Marked as ready")
                    session.get_task_status(task).mark_as_ready()
            else:
                ctx.log_warning(
                    "One or more readiness checks did not complete successfully."
                )

        except asyncio.TimeoutError as e:
            ctx.log_error(
                f"Readiness checks exceeded the {readiness_timeout}s aggregate "
                "timeout (TASK_READINESS_TIMEOUT); failing task"
            )
            readiness_error = e
        except Exception as e:
            ctx.log_error(f"Readiness check failed with exception: {e}")
            readiness_error = e

        if not readiness_passed:
            # Fail fast. A readiness check that exhausted its own retries means
            # the task's service is broken; deferring the (possibly never-ending)
            # action would leave the whole run hanging in wait_deferred with no
            # error exit.
            ctx.log_error("Readiness failed; cancelling action and failing task")
            action_coro.cancel()
            action_error: BaseException | None = None
            try:
                await action_coro
            except asyncio.CancelledError:
                pass
            except BaseException as e:
                action_error = e
            task_status = session.get_task_status(task)
            if not task_status.is_permanently_failed and not task_status.is_completed:
                # Same terminal bookkeeping as the retry loop's final attempt.
                # Skipped when the action already reached a terminal state:
                # permanently failed → the retry loop already ran the fallbacks;
                # completed → the action succeeded and its successors already
                # ran, so stacking permanent failure and firing fallbacks after
                # them would be contradictory. The readiness error still
                # propagates below, so the run fails visibly either way.
                task_status.mark_as_permanently_failed()
                skip_successors(task, session)
                await run_async(execute_fallbacks(task, session))
            if action_error is not None:
                # The action's own crash is usually why readiness failed —
                # surface it as the root cause, not the readiness symptom.
                raise action_error
            if readiness_error is not None:
                raise readiness_error
            raise RuntimeError(
                f"Readiness checks for task '{task.name}' did not complete"
            )

        # Defer the main action coroutine; it will be awaited later if needed
        session.defer_action(task, action_coro)

        # Start monitoring only if readiness passed and monitoring is enabled
        if readiness_passed and monitor_readiness:
            # lazy: circular — zrb.task.base.monitoring imports from this module.
            from zrb.task.base.monitoring import monitor_task_readiness

            monitor_coro = asyncio.create_task(
                run_async(monitor_task_readiness(task, session, action_coro))
            )
            session.defer_monitoring(task, monitor_coro)

        # The result here is primarily about readiness check completion.
        # The actual task result is handled by the deferred action_coro.
        return None
    except (asyncio.CancelledError, KeyboardInterrupt, GeneratorExit):
        action_coro.cancel()
        raise


async def execute_action_with_retry(task: "BaseTask", session: AnySession) -> Any:
    """
    Executes the task's core action (`_exec_action`) with retry logic,
    handling success (triggering successors) and failure (triggering fallbacks).
    """
    ctx = task.get_ctx(session)
    retries = task.retries
    retry_period = task.retry_period
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
            # We call the task's exec_action method directly here.
            result = await run_async(task.exec_action(ctx))

            ctx.log_info("Marked as completed")
            session.get_task_status(task).mark_as_completed()

            # Store result in XCom
            task_xcom: Xcom | None = ctx.xcom.get(task.name)
            if task_xcom is not None:
                task_xcom.push(result)

            # Skip fallbacks and execute successors on success
            skip_fallbacks(task, session)
            await run_async(execute_successors(task, session))
            return result

        except (asyncio.CancelledError, KeyboardInterrupt, GeneratorExit):
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
                ctx.log_error(traceback.format_exc())
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
    action = task.action
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


async def _execute_task_group(
    task: "BaseTask",
    session: "AnySession",
    task_list: list,
    group_name: str,
) -> None:
    """Executes a list of tasks concurrently, logging with the given group name."""
    ctx = task.get_ctx(session)
    if task_list:
        ctx.log_info(f"Executing {len(task_list)} {group_name}(s)")
        coros = [run_async(t.exec_chain(session)) for t in task_list]
        await gather_isolated(*coros)
    else:
        ctx.log_debug(f"No {group_name}s to execute.")


def _skip_task_group(
    task: "BaseTask",
    session: "AnySession",
    task_list: list,
    group_name: str,
) -> None:
    """Marks a list of tasks as skipped, logging with the given group name."""
    ctx = task.get_ctx(session)
    if task_list:
        ctx.log_info(f"Skipping {len(task_list)} {group_name}(s)")
        for t in task_list:
            if not session.get_task_status(t).is_skipped:
                session.get_task_status(t).mark_as_skipped()


async def execute_successors(task: "BaseTask", session: "AnySession"):
    """Executes all successor tasks."""
    await _execute_task_group(task, session, task.successors, "successor")


def skip_successors(task: "BaseTask", session: AnySession):
    """Marks all successor tasks as skipped."""
    _skip_task_group(task, session, task.successors, "successor")


async def execute_fallbacks(task: "BaseTask", session: AnySession):
    """Executes all fallback tasks."""
    await _execute_task_group(task, session, task.fallbacks, "fallback")


def skip_fallbacks(task: "BaseTask", session: AnySession):
    """Marks all fallback tasks as skipped."""
    _skip_task_group(task, session, task.fallbacks, "fallback")
