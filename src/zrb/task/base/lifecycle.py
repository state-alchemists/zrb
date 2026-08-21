"""Run/cleanup entry points for `BaseTask`: `run`, `async_run`, `exec_root_tasks`.

Composed into `BaseTask` as `self._base_lifecycle`. Holds a direct reference
to the sibling `BaseTaskContext` part (constructed first, so it is available
at `BaseTaskLifecycle.__init__` time) to seed the session's shared context
before the root tasks execute.
"""

import asyncio
from typing import TYPE_CHECKING, Any

from zrb.context.print_fn import PrintFn
from zrb.context.shared_context import SharedContext
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.util.run import gather_isolated, run_async

if TYPE_CHECKING:
    from zrb.task.base.base_task import BaseTask
    from zrb.task.base.context import BaseTaskContext


class BaseTaskLifecycle:
    """Drives a `BaseTask` run from process entry to session termination."""

    def __init__(self, task: "BaseTask", base_context: "BaseTaskContext") -> None:
        self._task = task
        self._base_context = base_context

    async def run_and_cleanup(
        self,
        session: AnySession | None = None,
        print_fn: PrintFn | None = None,
        str_kwargs: dict[str, str] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """
        Wrapper for async_run that ensures session termination and cleanup of
        other concurrent asyncio tasks. This is the main entry point for `task.run()`.
        """
        task = self._task
        if session is None:
            session = Session(shared_ctx=SharedContext(print_fn=print_fn))

        main_task_coro = asyncio.create_task(
            self.run_task_async(session, print_fn, str_kwargs, kwargs)
        )

        ctx = None
        try:
            result = await main_task_coro
            return result
        except (asyncio.CancelledError, KeyboardInterrupt) as e:
            ctx = task.get_ctx(session)
            ctx.log_warning(f"Run cancelled/interrupted: {e}")
            raise
        finally:
            if session and not session.is_terminated:
                ctx = task.get_ctx(session)
                ctx.log_info("Terminating session after run completion/error.")
                session.terminate()
            # Be cautious with blanket cancellation if other background tasks are expected
            try:
                pending = [
                    t
                    for t in asyncio.all_tasks()
                    if t is not main_task_coro and not t.done()
                ]
                if pending:
                    ctx = task.get_ctx(session)
                    ctx.log_debug(
                        f"Cleaning up {len(pending)} pending asyncio tasks..."
                    )
                    for t in pending:
                        t.cancel()
                    try:
                        # Give cancelled tasks a moment to process cancellation
                        await asyncio.wait(pending, timeout=1.0)
                    except asyncio.CancelledError:
                        # Expected if tasks handle cancellation promptly
                        pass
                    except Exception as cleanup_exc:
                        if ctx is not None:
                            ctx.log_warning(f"Error during task cleanup: {cleanup_exc}")
            except RuntimeError as cleanup_exc:
                if ctx is not None:
                    ctx.log_warning(f"Error during task cleanup: {cleanup_exc}")

    async def run_task_async(
        self,
        session: AnySession | None = None,
        print_fn: PrintFn | None = None,
        str_kwargs: dict[str, str] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """
        Asynchronous entry point for running a task (`task.async_run()`).
        Sets up the session and initiates the root task execution chain.
        """
        task = self._task
        if session is None:
            session = Session(shared_ctx=SharedContext(print_fn=print_fn))

        self._base_context.fill_shared_context_inputs(
            session.shared_ctx, str_kwargs, kwargs
        )
        self._base_context.fill_shared_context_envs(session.shared_ctx)

        result = await task.exec_root_tasks(session)
        return result

    async def execute_root_tasks(self, session: AnySession):
        """
        Identifies and executes the root tasks required for the main task,
        manages session state logging, and handles overall execution flow.
        """
        task = self._task
        session.set_main_task(task)
        session.state_logger.write(session.as_state_log())
        ctx = task.get_ctx(session)

        log_state_task = None
        try:
            log_state_task = asyncio.create_task(self.log_session_state(session))

            root_tasks = [
                t for t in session.get_root_tasks(task) if session.is_allowed_to_run(t)
            ]

            if not root_tasks:
                ctx.log_info("No root tasks to execute for this task.")
                session.terminate()
                return None

            ctx.log_info(f"Executing {len(root_tasks)} root task(s)")
            root_task_coros = [
                run_async(root_task.exec_chain(session)) for root_task in root_tasks
            ]

            await gather_isolated(*root_task_coros)

            ctx.log_info("Waiting for deferred actions...")
            await session.wait_deferred()
            ctx.log_info("Deferred actions complete.")

            session.terminate()
            if log_state_task and not log_state_task.done():
                await log_state_task
            ctx.log_info("Session finished.")
            return session.final_result

        except (asyncio.CancelledError, KeyboardInterrupt):
            ctx.log_warning("Session execution cancelled or interrupted.")
            # Propagate: swallowing cancellation here makes a cancelled session
            # look like a successful run to every caller (`await llm_task` returns
            # None instead of raising). Session termination happens in finally.
            raise
        finally:
            if not session.is_terminated:
                session.terminate()
            if log_state_task:
                if not log_state_task.done():
                    log_state_task.cancel()
                    try:
                        await log_state_task
                    except asyncio.CancelledError:
                        pass
                session.state_logger.write(session.as_state_log())
            else:
                session.state_logger.write(session.as_state_log())

            ctx.log_debug(f"Final session state: {session}")

    async def log_session_state(self, session: AnySession):
        """
        Periodically logs the session state until the session is terminated.
        """
        task = self._task
        try:
            while not session.is_terminated:
                session.state_logger.write(session.as_state_log())
                await asyncio.sleep(0.1)  # ~10 state log writes per second
            session.state_logger.write(session.as_state_log())
        except (asyncio.CancelledError, KeyboardInterrupt):
            try:
                session.state_logger.write(session.as_state_log())
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass  # Give up if interrupted again
            try:
                ctx = task.get_ctx(session)
                ctx.log_debug("Session state logger cancelled.")
            except Exception:
                pass  # Context may be unavailable during shutdown
        except Exception as e:
            try:
                ctx = task.get_ctx(session)
                ctx.log_error(f"Error in session state logger: {e}")
            except Exception:
                pass  # Context may be unavailable during shutdown
