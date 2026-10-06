import asyncio
import inspect
from typing import Any

# How long gather_fail_fast waits for cancelled siblings to unwind.
CANCEL_SETTLE_TIMEOUT = 5.0


async def run_async(value: Any) -> Any:
    """Await `value` if it's a Task/awaitable, else return it unchanged."""
    if isinstance(value, asyncio.Task):
        return await value
    if inspect.isawaitable(value):
        return await value
    return value


async def gather_isolated(*coros: Any) -> list[Any]:
    """Gather coros, letting every sibling settle before surfacing an error.

    Unlike plain ``asyncio.gather``, no sibling is left running orphaned:
    every coroutine completes, then the first exception is re-raised. Use
    ``gather_fail_fast`` where a sibling may never return on its own.
    """
    results = await asyncio.gather(*coros, return_exceptions=True)
    for r in results:
        if isinstance(r, BaseException):
            raise r
    return results


async def gather_fail_fast(*coros: Any) -> list[Any]:
    """Gather coros, cancelling the siblings when one of them fails.

    For siblings that may never return on their own (readiness checks,
    monitoring loops), where ``gather_isolated`` would hang. The unwind is
    capped at ``CANCEL_SETTLE_TIMEOUT``: ``asyncio.wait`` (unlike ``gather``)
    hands a cancellation straight back even when a child shields its cleanup,
    which keeps ``CFG.TASK_READINESS_TIMEOUT`` a real ceiling.
    """
    if not coros:
        return []
    tasks = [asyncio.ensure_future(coro) for coro in coros]
    pending = set(tasks)
    while pending:
        try:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
        except BaseException:
            # Cancellation aimed at us. Settle the children before unwinding.
            await _cancel_and_settle(tasks)
            raise
        # FIRST_COMPLETED: FIRST_EXCEPTION treats a cancelled child as a normal
        # completion and keeps waiting. Scanned in argument order so the
        # failure raised is the one plain gather would raise.
        failed = next(
            (t for t in tasks if t in done and (t.cancelled() or t.exception())),
            None,
        )
        if failed is not None:
            await _cancel_and_settle(tasks)
            return await failed  # re-raises the failure (or its CancelledError)
    return [task.result() for task in tasks]


async def _cancel_and_settle(tasks: "list[asyncio.Task[Any]]") -> None:
    """Cancel *tasks* and wait, up to ``CANCEL_SETTLE_TIMEOUT``, for them to
    unwind."""
    for task in tasks:
        task.cancel()
    try:
        await asyncio.wait(tasks, timeout=CANCEL_SETTLE_TIMEOUT)
    except BaseException:
        # A second cancellation landing mid-settle must not replace the outcome
        # the caller is about to raise.
        pass
