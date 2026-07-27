import asyncio
import inspect
from typing import Any

# How long gather_fail_fast waits for cancelled siblings to unwind.
_CANCEL_SETTLE_TIMEOUT = 5.0


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
    """Gather coros, letting every sibling settle before surfacing an error.

    Plain ``asyncio.gather`` propagates the first exception immediately, leaving
    the other coroutines running orphaned. Here every coroutine runs to
    completion, then the first exception is re-raised — same fail-fast contract
    for callers (cancellation included, matching plain gather), no orphaned
    siblings.

    This is the right shape for peer work that must not be cut short because a
    peer failed: successors, fallbacks, deferred actions. Use
    ``gather_fail_fast`` only where a sibling may never return on its own.
    """
    results = await asyncio.gather(*coros, return_exceptions=True)
    for r in results:
        if isinstance(r, BaseException):
            raise r
    return results


async def gather_fail_fast(*coros: Any) -> list[Any]:
    """Gather coros, cancelling the siblings when one of them fails.

    ``gather_isolated`` waits for every sibling to settle, which deadlocks when a
    sibling never returns on its own: a readiness check polls until it succeeds
    (``HttpCheck``/``TcpCheck`` never complete by themselves), so waiting for it
    after a peer has already failed hangs the caller forever. Here the first
    failure cancels the siblings instead.

    Cancellation of *this* coroutine is propagated the same way, so callers see
    plain-gather semantics with no orphans left behind.

    Prefer ``gather_isolated`` — cancelling peers is a real behavior difference,
    only correct when a peer's own completion is not something to wait for.
    """
    tasks = [asyncio.ensure_future(coro) for coro in coros]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        # Settle the cancellations before unwinding; a still-cancelling task
        # outliving this frame is the orphan we are trying to avoid. Capped: a
        # sibling that shields its cleanup must not turn this into the very hang
        # the cancellation exists to prevent.
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=_CANCEL_SETTLE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            pass
        raise
