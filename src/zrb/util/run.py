import asyncio
import inspect
from typing import Any


async def run_async(value: Any) -> Any:
    """
    Run a value asynchronously, awaiting if it's awaitable or returning it directly.

    Args:
        value (Any): The value to run. Can be awaitable or not.

    Returns:
        Any: The result of the awaited value or the value itself if not awaitable.
    """
    if isinstance(value, asyncio.Task):
        return await value
    if inspect.isawaitable(value):
        return await value
    return value


async def gather_isolated(*coros: Any) -> list[Any]:
    """Gather coros, cancelling the siblings when one of them fails.

    Plain ``asyncio.gather`` propagates the first exception immediately but
    leaves the other coroutines running orphaned. Waiting for them all instead
    (``return_exceptions=True``) fixes the orphans and loses the fail-fast: a
    sibling that never returns — a monitoring loop, a readiness check that polls
    until it succeeds, a long-running task body — would keep the run alive
    forever after another has already failed.

    So: fail fast like plain gather, then cancel the siblings and let their
    cancellation settle before re-raising. Cancellation of *this* coroutine is
    propagated the same way, so callers see plain-gather semantics with no
    orphans left behind.
    """
    tasks = [asyncio.ensure_future(coro) for coro in coros]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        # Settle the cancellations before unwinding; a still-cancelling task
        # outliving this frame is the orphan we are trying to avoid.
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
