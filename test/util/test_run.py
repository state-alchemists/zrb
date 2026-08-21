import asyncio

import pytest

from zrb.util.run import gather_fail_fast, gather_isolated, run_async


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
async def test_gather_isolated_lets_siblings_finish_before_surfacing_the_error():
    # gather_isolated's contract: peers are never cut short. Successors,
    # fallbacks and deferred actions all run through it, and a failing peer must
    # not cancel the work the others were asked to do.
    finished = []

    async def slow_ok():
        await asyncio.sleep(0.05)
        finished.append("slow")
        return "slow"

    async def fast_fail():
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError, match="fail"):
        await gather_isolated(slow_ok(), fast_fail())
    assert finished == ["slow"]


@pytest.mark.asyncio
async def test_gather_isolated_propagates_own_cancellation():
    async def child():
        await asyncio.sleep(30)

    task = asyncio.ensure_future(gather_isolated(child(), child()))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_gather_fail_fast_cancels_siblings_instead_of_orphaning_them():
    # The whole point of the fail-fast helper: a failing sibling must neither
    # orphan the others (plain gather) nor be waited on (gather_isolated).
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
        await gather_fail_fast(slow_ok(), fast_fail())
    assert cancelled == ["slow"]


@pytest.mark.asyncio
async def test_gather_fail_fast_next_to_a_never_ending_sibling():
    # Why readiness checks need this shape: waiting for every sibling to settle
    # means a non-terminating sibling — HttpCheck/TcpCheck poll until they
    # succeed — keeps the run alive forever after another check already failed.
    async def forever():
        while True:
            await asyncio.sleep(0.01)

    async def boom():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await asyncio.wait_for(gather_fail_fast(forever(), boom()), timeout=2)


@pytest.mark.asyncio
async def test_gather_fail_fast_returns_results_in_order():
    async def value(v):
        await asyncio.sleep(0.01)
        return v

    assert await gather_fail_fast(value(1), value(2), value(3)) == [1, 2, 3]


@pytest.mark.asyncio
async def test_gather_fail_fast_propagates_own_cancellation_and_cancels_children():
    cancelled = []

    async def child():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append("child")
            raise

    task = asyncio.ensure_future(gather_fail_fast(child(), child()))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled == ["child", "child"]


@pytest.mark.asyncio
async def test_gather_fail_fast_surfaces_a_cancelled_child_without_waiting():
    # A child cancelled from outside (session teardown cancelling one deferred
    # task) must fail fast like any other failure. asyncio.wait's
    # FIRST_EXCEPTION does NOT count a cancellation as an exception, so waiting
    # on that alone would block on the surviving siblings — the exact hang this
    # helper exists to prevent.
    cancelled = []

    async def child(name):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append(name)
            raise

    victim = asyncio.ensure_future(child("victim"))
    gathered = asyncio.ensure_future(gather_fail_fast(victim, child("sibling")))
    await asyncio.sleep(0.01)
    victim.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(gathered, timeout=2)
    assert sorted(cancelled) == ["sibling", "victim"]


@pytest.mark.asyncio
async def test_gather_fail_fast_stays_bounded_when_a_child_shields_its_cleanup(
    monkeypatch,
):
    # An enclosing wait_for must remain a real ceiling. Awaiting the children
    # through asyncio.gather did not: a gather being cancelled cancels its
    # children and then waits for them, so a child that shields its cleanup held
    # the cancellation pending and CFG.TASK_READINESS_TIMEOUT overshot by however
    # long that child took.
    monkeypatch.setattr("zrb.util.run.CANCEL_SETTLE_TIMEOUT", 0.2)

    async def shielded():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            await asyncio.sleep(30)  # refuses to unwind

    loop = asyncio.get_running_loop()
    started = loop.time()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(gather_fail_fast(shielded(), shielded()), timeout=0.1)
    # timeout + settle cap, not the 30s the children would have taken.
    assert loop.time() - started < 2
