import asyncio
import inspect
from typing import Any

# How long gather_fail_fast waits for cancelled siblings to unwind.
_CANCEL_SETTLE_TIMEOUT = 5.0


async def run_async(value: Any) -> Any:
    """Await `value` if it's a Task/awaitable, else return it unchanged."""
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
    peer failed: successors, fallbacks, task chains, root tasks. Use
    ``gather_fail_fast`` where a sibling may never return on its own.
    """
    results = await asyncio.gather(*coros, return_exceptions=True)
    for r in results:
        if isinstance(r, BaseException):
            raise r
    return results


async def gather_fail_fast(*coros: Any) -> list[Any]:
    """Gather coros, cancelling the siblings when one of them fails.

    ``gather_isolated`` waits for every sibling to settle, which deadlocks when a
    sibling never returns on its own — a readiness check that polls until it
    succeeds (``HttpCheck``/``TcpCheck``), a deferred long-running task body, a
    ``Scheduler``/``BaseTrigger`` monitoring loop. Waiting for one of those after
    a peer has already failed hangs the caller forever. Here the first failure
    cancels the siblings instead.

    Cancellation of *this* coroutine is propagated the same way, so callers see
    plain-gather semantics with no orphans left behind — and, unlike plain
    gather, the unwind is bounded in *both* directions (see below).

    ``asyncio.wait``, not ``asyncio.gather``, for the primary await: a gather
    being cancelled cancels its children and then waits for them, so a child
    that shields its cleanup keeps the cancellation pending indefinitely and an
    enclosing ``wait_for`` overshoots its timeout by however long that child
    takes. ``asyncio.wait`` hands the cancellation straight back, which lets the
    settle below actually apply its cap. This is what makes
    ``CFG.TASK_READINESS_TIMEOUT`` a real ceiling on the readiness fan-out.

    Prefer ``gather_isolated`` — cancelling peers is a real behavior difference,
    only correct when a peer's own completion is not something to wait for.
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
        # FIRST_COMPLETED, not FIRST_EXCEPTION: the latter treats a *cancelled*
        # child as an ordinary completion and keeps waiting for the rest, so a
        # session teardown that cancels one deferred task would block on its
        # siblings — the hang this helper exists to prevent. Scanned in argument
        # order (`done` is an unordered set) so the reported failure is the same
        # one plain gather would have raised.
        failed = next(
            (t for t in tasks if t in done and (t.cancelled() or t.exception())),
            None,
        )
        if failed is not None:
            await _cancel_and_settle(tasks)
            return await failed  # re-raises the failure (or its CancelledError)
    return [task.result() for task in tasks]


async def _cancel_and_settle(tasks: "list[asyncio.Task[Any]]") -> None:
    """Cancel *tasks* and wait, briefly, for them to unwind.

    A still-cancelling task outliving the caller's frame is the orphan this
    exists to avoid. Capped: a sibling that shields its cleanup must not turn
    the settle into the very hang the cancellation exists to prevent.
    """
    for task in tasks:
        task.cancel()
    try:
        await asyncio.wait(tasks, timeout=_CANCEL_SETTLE_TIMEOUT)
    except BaseException:
        # A second cancellation landing mid-settle must not replace the outcome
        # the caller is about to raise.
        pass
