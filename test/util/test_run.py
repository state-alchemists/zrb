import asyncio

import pytest

from zrb.util.run import gather_isolated, run_async


@pytest.mark.asyncio
async def test_run_async_with_direct_value():
    assert await run_async(123) == 123
    assert await run_async("hello") == "hello"
    assert await run_async(None) is None


@pytest.mark.asyncio
async def test_run_async_with_coroutine():
    async def sample_coro():
        return "result"

    assert await run_async(sample_coro()) == "result"


@pytest.mark.asyncio
async def test_run_async_with_task():
    async def sample_coro():
        await asyncio.sleep(0.01)
        return "task result"

    task = asyncio.create_task(sample_coro())
    assert await run_async(task) == "task result"


@pytest.mark.asyncio
async def test_run_async_with_awaitable_object():
    class AwaitableObj:
        def __await__(self):
            yield
            return "awaitable result"

    assert await run_async(AwaitableObj()) == "awaitable result"


@pytest.mark.asyncio
async def test_gather_isolated_returns_all_results_in_order():
    async def value(x):
        await asyncio.sleep(0)
        return x

    assert await gather_isolated(value(1), value(2), value(3)) == [1, 2, 3]


@pytest.mark.asyncio
async def test_gather_isolated_reraises_first_exception():
    async def boom():
        raise ValueError("boom")

    async def ok():
        return "ok"

    with pytest.raises(ValueError, match="boom"):
        await gather_isolated(boom(), ok())


@pytest.mark.asyncio
async def test_gather_isolated_cancels_siblings_instead_of_orphaning_them():
    # The whole point of the helper: a failing sibling must not orphan the
    # others. Plain asyncio.gather would propagate on first exception and leave
    # the slow sibling running; here it is cancelled and settled.
    cancelled = []

    async def slow_ok():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append("slow")
            raise
        return "slow"  # pragma: no cover - cancelled before returning

    async def fast_fail():
        await asyncio.sleep(0.01)
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError, match="fail"):
        await gather_isolated(slow_ok(), fast_fail())
    assert cancelled == ["slow"]


@pytest.mark.asyncio
async def test_gather_isolated_fails_fast_next_to_a_never_ending_sibling():
    # Regression: waiting for every sibling to settle (return_exceptions=True)
    # meant a non-terminating sibling — a monitoring loop, a readiness check
    # that polls until it succeeds — kept the run alive forever after another
    # coroutine had already failed. The failure must surface regardless.
    async def forever():
        while True:
            await asyncio.sleep(0.01)

    async def boom():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await asyncio.wait_for(gather_isolated(forever(), boom()), timeout=2)


@pytest.mark.asyncio
async def test_gather_isolated_returns_results_in_order():
    async def value(v):
        await asyncio.sleep(0.01)
        return v

    assert await gather_isolated(value(1), value(2), value(3)) == [1, 2, 3]


@pytest.mark.asyncio
async def test_gather_isolated_propagates_own_cancellation_and_cancels_children():
    cancelled = []

    async def child():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append("child")
            raise

    task = asyncio.ensure_future(gather_isolated(child(), child()))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled == ["child", "child"]
