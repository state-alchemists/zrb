"""Run blocking callables without making interpreter shutdown wait for them."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from functools import partial
from typing import TypeVar, cast

_T = TypeVar("_T")


def _let_go(on_orphan: Callable[[_T], None] | None, value: object) -> None:
    """Hand a value nobody is waiting for to *on_orphan*, when there is one."""
    if on_orphan is not None:
        on_orphan(cast("_T", value))


def _let_go_if_it_landed(
    future: "asyncio.Future[_T]", on_orphan: Callable[[_T], None] | None
) -> None:
    """Let go of what *future* holds, unless it holds a failure or nothing.

    Reading the exception off is what keeps a call that failed after its caller
    was cancelled from being reported as one whose result was never retrieved.
    """
    if future.cancelled():
        return
    if future.exception() is not None:
        return
    _let_go(on_orphan, future.result())


async def run_in_daemon(
    func: Callable[..., _T],
    *args: object,
    name: str = "zrb-daemon",
    on_orphan: Callable[[_T], None] | None = None,
) -> _T:
    """Run *func* on a daemon thread and await its result.

    Cancellation stops waiting for the callable but cannot stop code already
    running in the thread. The daemon thread is intentional: a blocking native
    call that outlives its cancelled caller must not hold interpreter shutdown.

    What such a call produces it still produces, by which time nobody is waiting
    for it — a loaded model, an open socket. *on_orphan*, when given, is handed
    that value where it lands, so it is let go of rather than left to the
    collector. It runs on the event loop while there is still one, and on the
    callable's own thread when the loop is already gone.
    """
    loop = asyncio.get_running_loop()
    result: asyncio.Future[_T] = loop.create_future()

    def settle(setter: Callable[..., None], value: object) -> None:
        if not result.done():
            setter(value)

    def post(setter: Callable[..., None], value: object) -> None:
        try:
            loop.call_soon_threadsafe(settle, setter, value)
        except RuntimeError:
            # The loop closed while the daemon call was still unwinding, so
            # nobody will read this result: let it go where it landed.
            _let_go(on_orphan, value)

    def run() -> None:
        try:
            value = func(*args)
        except BaseException as error:
            post(result.set_exception, error)
        else:
            post(result.set_result, value)

    threading.Thread(target=run, name=name, daemon=True).start()
    try:
        # Shielded, so a cancelled wait does not cancel the call: what the thread
        # is running cannot be cancelled with it, and its result has to stay
        # reachable for the orphan to be let go of.
        return await asyncio.shield(result)
    except asyncio.CancelledError:
        result.add_done_callback(partial(_let_go_if_it_landed, on_orphan=on_orphan))
        raise
