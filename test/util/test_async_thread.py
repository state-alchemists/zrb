"""Daemon-thread results and orphan handling."""

import asyncio
import threading
import time

import pytest

from zrb.util.async_thread import run_in_daemon

#: Test operations must finish well before this timeout.
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
    """Cancellation must not leave a worker blocking process exit."""
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
    """Cancellation is not held hostage by blocked native code."""
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
    """An unstoppable call sends its late result to the orphan disposer."""
    reached = threading.Event()
    release = threading.Event()
    let_go: list[str] = []

    def load() -> str:
        reached.set()
        release.wait(_TIMEOUT)
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
    """Only orphaned values go to the disposer."""
    let_go: list[int] = []

    assert await run_in_daemon(lambda: 3, on_orphan=let_go.append) == 3
    await asyncio.sleep(0)

    assert let_go == []


async def _until_event(event: threading.Event, timeout: float = _TIMEOUT) -> None:
    """Yield until *event* is set or the timeout expires."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not event.is_set() and loop.time() < deadline:
        await asyncio.sleep(0.01)
    assert event.is_set(), "the event was never set"


def _land_with_no_loop_left(func, on_orphan) -> None:
    """Cancel *func*, close its loop, then join the worker before returning."""
    entered = threading.Event()
    release = threading.Event()
    threads: list[threading.Thread] = []

    def held() -> object:
        threads.append(threading.current_thread())
        entered.set()
        assert release.wait(_TIMEOUT), "the worker was never released"
        return func()

    loop = asyncio.new_event_loop()
    try:
        running = loop.create_task(run_in_daemon(held, on_orphan=on_orphan))
        loop.run_until_complete(_until_event(entered))
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            loop.run_until_complete(running)
    finally:
        loop.close()

    release.set()
    worker = threads[0]
    worker.join(_TIMEOUT)
    assert not worker.is_alive(), "the worker never landed"


def test_a_result_that_lands_after_the_loop_closed_is_let_go():
    """Nowhere to deliver to, so the result is let go where it landed."""
    let_go: list[object] = []

    _land_with_no_loop_left(lambda: "a loaded model", let_go.append)

    assert let_go == ["a loaded model"]


def test_a_failure_that_lands_after_the_loop_closed_is_not_let_go():
    """Failures are not orphan results, so *on_orphan* must not receive them."""
    let_go: list[object] = []

    def no_model() -> object:
        raise ValueError("no model at that path")

    _land_with_no_loop_left(no_model, let_go.append)

    assert let_go == []
