import asyncio
from typing import Any

from zrb.context.shared_context import SharedContext
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.task.base.context import fill_shared_context_envs, fill_shared_context_inputs
from zrb.util.run import run_async


async def run_and_cleanup(
    task: AnyTask,
    session: AnySession | None = None,
    str_kwargs: dict[str, str] = {},
) -> Any:
    """
    Wrapper for async_run that ensures session termination and cleanup of
    other concurrent asyncio tasks. This is the main entry point for `task.run()`.
    """
    # Ensure a session exists
    if session is None:
        session = Session(shared_ctx=SharedContext())

    # Create the main task execution coroutine
    main_task_coro = asyncio.create_task(run_task_async(task, session, str_kwargs))

    try:
        result = await main_task_coro
        return result
    except (asyncio.CancelledError, KeyboardInterrupt) as e:
        ctx = task.get_ctx(session)  # Get context for logging
        ctx.log_warning(f"Run cancelled/interrupted: {e}")
        raise  # Re-raise to propagate
    finally:
        # Ensure session termination if it exists and wasn't terminated by the run
        if session and not session.is_terminated:
            ctx = task.get_ctx(session)  # Get context for logging
            ctx.log_info("Terminating session after run completion/error.")
            session.terminate()
        # Clean up other potentially running asyncio tasks (excluding the main one)
        # Be cautious with blanket cancellation if other background tasks are expected
        try:
            pending = [
                t
                for t in asyncio.all_tasks()
                if t is not main_task_coro and not t.done()
            ]
            if pending:
                ctx = task.get_ctx(session)  # Get context for logging
                ctx.log_debug(f"Cleaning up {len(pending)} pending asyncio tasks...")
                for t in pending:
                    t.cancel()
                try:
                    # Give cancelled tasks a moment to process cancellation
                    await asyncio.wait(pending, timeout=1.0)
                except asyncio.CancelledError:
                    # Expected if tasks handle cancellation promptly
                    pass
                except Exception as cleanup_exc:
                    # Log errors during cleanup if necessary
                    ctx.log_warning(f"Error during task cleanup: {cleanup_exc}")
        except RuntimeError as cleanup_exc:
            ctx.log_warning(f"Error during task cleanup: {cleanup_exc}")


async def run_task_async(
    task: AnyTask,
    session: AnySession | None = None,
    str_kwargs: dict[str, str] = {},
) -> Any:
    """
    Asynchronous entry point for running a task (`task.async_run()`).
    Sets up the session and initiates the root task execution chain.
    """
    if session is None:
        session = Session(shared_ctx=SharedContext())

    # Populate shared context with inputs and environment variables
    fill_shared_context_inputs(task, session.shared_ctx, str_kwargs)
    fill_shared_context_envs(session.shared_ctx)  # Inject OS env vars

    # Start the execution chain from the root tasks
    result = await task.exec_root_tasks(session)
    return result


async def execute_root_tasks(task: AnyTask, session: AnySession):
    """
    Identifies and executes the root tasks required for the main task,
    manages session state logging, and handles overall execution flow.
    """
    session.set_main_task(task)
    session.state_logger.write(session.as_state_log())  # Initial state log
    ctx = task.get_ctx(session)  # Get context early for logging

    log_state_task = None
    try:
        # Start background state logging
        log_state_task = asyncio.create_task(log_session_state(task, session))

        # Identify root tasks allowed to run
        root_tasks = [
            t for t in session.get_root_tasks(task) if session.is_allowed_to_run(t)
        ]

        if not root_tasks:
            ctx.log_info("No root tasks to execute for this task.")
            # If the main task itself should run even with no explicit roots?
            # Current logic seems to imply if no roots, nothing runs.
            session.terminate()  # Terminate if nothing to run
            return None

        ctx.log_info(f"Executing {len(root_tasks)} root task(s)")
        root_task_coros = [
            # Assuming exec_chain exists on AnyTask (it's abstract)
            run_async(root_task.exec_chain(session))
            for root_task in root_tasks
        ]

        # Wait for all root chains to complete
        await asyncio.gather(*root_task_coros)

        # Wait for any deferred actions (like long-running task bodies)
        ctx.log_info("Waiting for deferred actions...")
        await session.wait_deferred()
        ctx.log_info("Deferred actions complete.")

        # Final termination and logging
        session.terminate()
        if log_state_task and not log_state_task.done():
            await log_state_task  # Ensure final state is logged
        ctx.log_info("Session finished.")
        return session.final_result

    except IndexError:
        # This might occur if get_root_tasks fails unexpectedly
        ctx.log_error(
            "IndexError during root task execution, potentially session issue."
        )
        session.terminate()  # Ensure termination on error
        return None
    except (asyncio.CancelledError, KeyboardInterrupt):
        ctx.log_warning("Session execution cancelled or interrupted.")
        # Session termination happens in finally block
        return None  # Indicate abnormal termination
    finally:
        # Ensure termination and final state logging regardless of outcome
        if not session.is_terminated:
            session.terminate()
        # Ensure the state logger task is awaited/cancelled properly
        if log_state_task:
            if not log_state_task.done():
                log_state_task.cancel()
                try:
                    await log_state_task
                except asyncio.CancelledError:
                    pass  # Expected cancellation
            # Log final state after ensuring logger task is finished
            session.state_logger.write(session.as_state_log())
        else:
            # Log final state even if logger task didn't start
            session.state_logger.write(session.as_state_log())

        ctx.log_debug(f"Final session state: {session}")  # Log final session details


async def log_session_state(task: AnyTask, session: AnySession):
    """
    Periodically logs the session state until the session is terminated.
    """
    try:
        while not session.is_terminated:
            session.state_logger.write(session.as_state_log())
            await asyncio.sleep(0.1)  # Log interval
        # Log one final time after termination signal
        session.state_logger.write(session.as_state_log())
    except asyncio.CancelledError:
        # Log final state on cancellation too
        session.state_logger.write(session.as_state_log())
        ctx = task.get_ctx(session)
        ctx.log_debug("Session state logger cancelled.")
    except Exception as e:
        # Log any unexpected errors in the logger itself
        ctx = task.get_ctx(session)
        ctx.log_error(f"Error in session state logger: {e}")
