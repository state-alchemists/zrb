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

    Reading the exception prevents an unhandled-failure report after cancellation.
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

    Cancellation stops waiting but cannot stop code already running in the
    thread. *on_orphan* receives a completed value after cancellation, on the
    event loop when available or on the callable's thread after loop shutdown.
    """
    loop = asyncio.get_running_loop()
    result: asyncio.Future[_T] = loop.create_future()

    def settle(setter: Callable[..., None], value: object) -> None:
        if not result.done():
            setter(value)

    def succeed(value: object) -> None:
        try:
            loop.call_soon_threadsafe(settle, result.set_result, value)
        except RuntimeError:
            # The loop closed while the daemon call was still unwinding, so
            # nobody will read this: let the result go where it landed.
            _let_go(on_orphan, value)

    def fail(error: BaseException) -> None:
        try:
            loop.call_soon_threadsafe(settle, result.set_exception, error)
        except RuntimeError:
            # No caller remains; *on_orphan* receives results, not failures.
            return

    def run() -> None:
        try:
            value = func(*args)
        except BaseException as error:
            fail(error)
        else:
            succeed(value)

    threading.Thread(target=run, name=name, daemon=True).start()
    try:
        # Shielding keeps cancellation from cancelling the thread's future.
        return await asyncio.shield(result)
    except asyncio.CancelledError:
        result.add_done_callback(partial(_let_go_if_it_landed, on_orphan=on_orphan))
        raise
