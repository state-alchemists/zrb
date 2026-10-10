"""Thread-safe hook executor with per-hook timeouts."""

import asyncio
import atexit
import contextvars
import logging
import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, TypeVar, cast

from zrb.config.config import CFG
from zrb.llm.agent_state import current_tool_confirmation, current_ui
from zrb.llm.approval.approval_channel import current_approval_channel
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass
class HookExecutionResult:
    """A hook's outcome, with Claude Code compatible fields."""

    success: bool
    blocked: bool = False
    message: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    exit_code: int = 0
    decision: str | None = None  # "block", "allow", "deny", "ask"
    reason: str | None = None
    permission_decision: str | None = None  # "allow", "deny", "ask"
    permission_decision_reason: str | None = None
    additional_context: str | None = None
    updated_input: dict[str, Any] | None = None
    system_message: str | None = None
    replace_response: bool = False  # extended response replaces the original
    continue_execution: bool = True
    suppress_output: bool = False
    hook_specific_output: dict[str, Any] | None = None


class _HookRun:
    """One hook's run in its own event loop on a pool thread.

    `cancel` reaches into that loop; cancelling the caller's future alone would
    leave the hook running."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[Any] | None = None
        self._cancelled = False

    def can_start(self) -> bool:
        """Record the hook's loop for `cancel`; False if already cancelled."""
        with self._lock:
            if self._cancelled:
                return False
            self._loop = asyncio.get_running_loop()
            self._task = asyncio.current_task()
            return True

    def cancel(self) -> None:
        """Cancel the hook, whether it has started yet or not."""
        with self._lock:
            self._cancelled = True
            if self._loop is None or self._task is None:
                return
            try:
                self._loop.call_soon_threadsafe(self._task.cancel)
            except RuntimeError:
                pass  # its loop is closed: the hook already finished


class _DaemonHookExecutor:
    """Run submitted hooks on a bounded pool of daemon worker threads."""

    def __init__(self, max_workers: int, thread_name_prefix: str) -> None:
        self._thread_name_prefix = thread_name_prefix
        self._lock = threading.Lock()
        self._work_queue: queue.Queue[
            tuple[Future[object], Callable[..., object], tuple[object, ...]] | None
        ] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._shutting_down = False
        for worker_id in range(max_workers):
            worker = threading.Thread(
                target=self._worker,
                name=f"{self._thread_name_prefix}{worker_id}",
                daemon=True,
            )
            self._threads.append(worker)
            worker.start()

    def submit(self, fn: Callable[..., T], *args: object) -> Future[T]:
        future: Future[T] = Future()
        with self._lock:
            if self._shutting_down:
                raise RuntimeError("cannot schedule new futures after shutdown")
            self._work_queue.put(
                (cast(Future[object], future), cast(Callable[..., object], fn), args)
            )
        return future

    def _worker(self) -> None:
        while True:
            work = self._work_queue.get()
            try:
                if work is None:
                    return
                future, fn, args = work
                if not future.set_running_or_notify_cancel():
                    continue
                try:
                    future.set_result(fn(*args))
                except BaseException as error:
                    future.set_exception(error)
                    if isinstance(error, (KeyboardInterrupt, SystemExit)):
                        raise
            finally:
                self._work_queue.task_done()

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            self._shutting_down = True
            for _ in self._threads:
                self._work_queue.put(None)
            threads = tuple(self._threads)
        if wait:
            for thread in threads:
                thread.join()


class ThreadPoolHookExecutor:
    """Thread-safe hook executor with per-hook timeouts (exit 0=success, 2=block)."""

    def __init__(
        self,
        max_workers: int = 10,
        default_timeout: float | None = None,
        cancel_grace_seconds: float = 5.0,
    ):
        if max_workers < 1:
            raise ValueError(
                "max_workers must be greater than 0; provide at least one worker"
            )
        self.max_workers = max_workers
        self.default_timeout = (
            default_timeout if default_timeout is not None else CFG.HOOKS_TIMEOUT / 1000
        )
        #: How long a cancelled or timed-out hook gets to finish once cancelled.
        self.cancel_grace_seconds = cancel_grace_seconds
        self._executor: _DaemonHookExecutor | None = None
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()

    def start(self):
        """Start the thread pool executor."""
        with self._lock:
            if self._executor is None:
                self._executor = _DaemonHookExecutor(
                    max_workers=self.max_workers, thread_name_prefix="zrb-hook-"
                )
                self._shutdown_event.clear()
                logger.debug(f"Hook executor started with {self.max_workers} workers")

    def shutdown(self, wait: bool = True):
        """Shutdown the thread pool executor."""
        with self._lock:
            if self._executor is not None:
                self._shutdown_event.set()
                self._executor.shutdown(wait=wait)
                self._executor = None
                logger.debug("Hook executor shutdown complete")

    @asynccontextmanager
    async def execution_context(self):
        """Context manager for hook execution."""
        try:
            self.start()
            yield self
        finally:
            # Don't shutdown automatically - let the manager handle lifecycle
            pass

    async def execute_hook(
        self,
        hook: HookCallable,
        context: HookContext,
        timeout: float | None = None,
    ) -> HookExecutionResult:
        """Run *hook* under *timeout* (default `self.default_timeout`); never raises
        except to propagate cancellation."""
        if self._shutdown_event.is_set():
            return HookExecutionResult(
                success=False, error="Hook executor is shutting down", exit_code=1
            )

        timeout = timeout or self.default_timeout
        run = _HookRun()

        try:
            self.start()
            assert self._executor is not None
            job: Future[HookExecutionResult] = self._executor.submit(
                _copy_context_for_hook().run, self._run_hook_sync, hook, context, run
            )
        except RuntimeError as e:  # shut down by another thread meanwhile
            return HookExecutionResult(success=False, error=str(e), exit_code=1)
        try:
            # Shielded: a cancel or timeout here stops the hook through `run`
            # and waits for it (`_stop`), rather than only ceasing to wait.
            return await asyncio.wait_for(
                asyncio.shield(asyncio.wrap_future(job)), timeout=timeout
            )

        except asyncio.CancelledError:
            await self._stop(run, job)
            raise
        except asyncio.TimeoutError:
            await self._stop(run, job)
            logger.warning(f"Hook execution timed out after {timeout}s")
            return HookExecutionResult(
                success=False,
                error=f"Hook execution timed out after {timeout}s",
                exit_code=124,
            )
        except Exception as e:
            logger.error(f"Error executing hook: {e}", exc_info=True)
            return HookExecutionResult(success=False, error=str(e), exit_code=1)

    async def _stop(self, run: "_HookRun", job: Future[HookExecutionResult]) -> None:
        """Cancel the hook and wait up to `cancel_grace_seconds` for it to finish.

        A hook blocked in a synchronous call is left running, with a warning."""
        run.cancel()
        if job.cancel():
            return
        done, _ = await asyncio.wait(
            [asyncio.wrap_future(job)], timeout=self.cancel_grace_seconds
        )
        if not done:
            logger.warning(
                "A cancelled hook is still running after %ss; it is left to finish.",
                self.cancel_grace_seconds,
            )

    def _run_hook_sync(
        self, hook: HookCallable, context: HookContext, run: "_HookRun"
    ) -> HookExecutionResult:
        """Run *hook* in a fresh event loop on the calling pool thread."""

        async def run_hook_async():
            if not run.can_start():
                return HookResult(success=False, output="Hook cancelled")
            try:
                return await hook(context)
            except asyncio.CancelledError:
                return HookResult(success=False, output="Hook cancelled")
            except Exception as e:
                logger.error(f"Error in hook execution: {e}", exc_info=True)
                return HookResult(success=False, output=str(e), should_stop=False)

        try:
            # asyncio.run() cleans up subprocess transports before closing the loop.
            hook_result = asyncio.run(run_hook_async())
            return self._parse_hook_result(hook_result)

        except Exception as e:
            logger.error(f"Error in hook execution setup: {e}", exc_info=True)
            return HookExecutionResult(success=False, error=str(e), exit_code=1)

    # Claude-Code modification key -> the `HookExecutionResult` attribute it sets.
    # `decision` is absent on purpose: it also flips `blocked`/`exit_code`.
    _MODIFICATION_FIELDS = {
        "reason": "reason",
        "permissionDecision": "permission_decision",
        "permissionDecisionReason": "permission_decision_reason",
        "additionalContext": "additional_context",
        "updatedInput": "updated_input",
        "systemMessage": "system_message",
        "replaceResponse": "replace_response",
        "continue": "continue_execution",
        "suppressOutput": "suppress_output",
        "hookSpecificOutput": "hook_specific_output",
    }

    def _parse_hook_result(self, result: HookResult) -> HookExecutionResult:
        """Convert a `HookResult` into a `HookExecutionResult`."""
        exec_result = HookExecutionResult(
            success=result.success, message=result.output, data=result.data or {}
        )

        if not result.success:
            if result.output:
                exec_result.error = result.output
            exec_result.exit_code = 1

        if result.should_stop:
            self._block(exec_result)

        if not result.modifications:
            return exec_result

        # HookManager reads modifications back out of `data` (manager.py).
        exec_result.data.update(result.modifications)
        if "decision" in result.modifications:
            exec_result.decision = result.modifications["decision"]
            if exec_result.decision == "block":
                self._block(exec_result)
        for key, attribute in self._MODIFICATION_FIELDS.items():
            if key in result.modifications:
                setattr(exec_result, attribute, result.modifications[key])
        return exec_result

    def _block(self, exec_result: HookExecutionResult) -> None:
        """Mark a result as blocking, in the form Claude Code expects."""
        exec_result.blocked = True
        exec_result.decision = "block"
        exec_result.exit_code = 2


_hook_executor: ThreadPoolHookExecutor | None = None
_executor_lock = threading.Lock()


def get_hook_executor() -> ThreadPoolHookExecutor:
    """Get or create the singleton hook executor (thread-safe)."""
    global _hook_executor
    if _hook_executor is None:
        with _executor_lock:
            if _hook_executor is None:
                _hook_executor = ThreadPoolHookExecutor()
                _hook_executor.start()
    return _hook_executor


def shutdown_hook_executor(wait: bool = True):
    """Shutdown the singleton hook executor (thread-safe)."""
    global _hook_executor
    with _executor_lock:
        if _hook_executor is not None:
            _hook_executor.shutdown(wait=wait)
            _hook_executor = None


# Never block interpreter exit on an in-flight hook.
atexit.register(shutdown_hook_executor, False)


def _copy_context_for_hook() -> contextvars.Context:
    """A copy of the caller's context for a pool-thread hook run.

    The UI, tool confirmation and approval channel are cleared: they are bound
    to the caller's event loop, and the hook runs in its own."""
    context = contextvars.copy_context()
    context.run(current_ui.set, None)
    context.run(current_tool_confirmation.set, None)
    context.run(current_approval_channel.set, None)
    return context
