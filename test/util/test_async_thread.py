"""Blocking work on a daemon thread: what it returns, and what becomes of a
result that arrives after nobody is waiting for it any more."""

import asyncio
import threading
import time

import pytest

from zrb.util.async_thread import run_in_daemon

#: Nothing here waits on a real model, so anything approaching this is a hang.
_TIMEOUT = 5.0


async def _until(predicate, timeout: float = _TIMEOUT) -> None:
    """Yield to the loop until *predicate* holds, or fail saying it never did."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate() and loop.time() < deadline:
        await asyncio.sleep(0.01)
    assert predicate(), "the condition never held"


@pytest.mark.asyncio
async def test_the_call_runs_off_the_loop_and_returns_its_value():
    assert await run_in_daemon(lambda: 7) == 7


@pytest.mark.asyncio
async def test_the_call_runs_on_a_daemon_thread():
    """A non-daemon thread that outlives its cancelled caller would block exit."""
    daemon_flags: list[bool] = []

    def record() -> None:
        daemon_flags.append(threading.current_thread().daemon)

    await run_in_daemon(record)

    assert daemon_flags == [True]


@pytest.mark.asyncio
async def test_a_failure_reaches_the_caller():
    def boom() -> None:
        raise ValueError("no model at that path")

    with pytest.raises(ValueError, match="no model at that path"):
        await run_in_daemon(boom)


@pytest.mark.asyncio
async def test_a_cancelled_wait_does_not_wait_out_a_blocked_call():
    """The whole point: cancellation is not held hostage by native code."""
    release = threading.Event()
    try:
        running = asyncio.create_task(run_in_daemon(release.wait))
        await asyncio.sleep(0.05)

        start = time.monotonic()
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running

        assert time.monotonic() - start < 2, "cancellation waited on the call"
    finally:
        release.set()


@pytest.mark.asyncio
async def test_a_result_that_lands_after_the_cancellation_is_let_go():
    """A call cannot be stopped, so what it produces has to be disposed of.

    A loaded model or an open socket outlives the wait that was cancelled. The
    caller names what becomes of it, and gets it where it lands.
    """
    reached = threading.Event()
    release = threading.Event()
    let_go: list[str] = []

    def load() -> str:
        reached.set()
        release.wait(_TIMEOUT)  # the load a cancelled wait walks away from
        return "a loaded model"

    try:
        running = asyncio.create_task(
            run_in_daemon(load, name="test-loader", on_orphan=let_go.append)
        )
        await _until(reached.is_set)

        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert let_go == [], "nothing has landed yet"

        release.set()
        await _until(lambda: bool(let_go))

        assert let_go == ["a loaded model"]
    finally:
        release.set()


@pytest.mark.asyncio
async def test_a_result_its_caller_read_is_not_let_go():
    """A value somebody waited for is theirs; only orphans go to the disposer."""
    let_go: list[int] = []

    assert await run_in_daemon(lambda: 3, on_orphan=let_go.append) == 3
    await asyncio.sleep(0)

    assert let_go == []
