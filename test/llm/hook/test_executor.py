import asyncio
import threading

import pytest

from zrb.llm.hook.executor import (
    ThreadPoolHookExecutor,
    get_hook_executor,
    shutdown_hook_executor,
)
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent


@pytest.mark.asyncio
async def test_executor_lifecycle():
    executor = ThreadPoolHookExecutor(max_workers=2)
    executor.start()

    async with executor.execution_context() as ctx:
        assert ctx == executor

    executor.shutdown()


@pytest.mark.asyncio
async def test_executor_execute_hook():
    executor = ThreadPoolHookExecutor()
    executor.start()

    async def sample_hook(ctx):
        return HookResult(success=True, output="Done")

    ctx = HookContext(
        event=HookEvent.SESSION_START, event_data={}, hook_event_name="start"
    )
    result = await executor.execute_hook(sample_hook, ctx)

    assert result.success is True
    assert result.message == "Done"
    executor.shutdown()


def _start_context():
    return HookContext(
        event=HookEvent.SESSION_START, event_data={}, hook_event_name="start"
    )


def _hook_that_waits(started: threading.Event, stopped: threading.Event):
    async def hook(ctx):
        started.set()
        try:
            await asyncio.sleep(30)  # a reviewer's model request, say
        finally:
            stopped.set()
        return HookResult(success=True)

    return hook


@pytest.mark.asyncio
async def test_a_timed_out_hook_is_cancelled_not_left_running():
    executor = ThreadPoolHookExecutor(default_timeout=1)
    executor.start()
    started, stopped = threading.Event(), threading.Event()

    result = await executor.execute_hook(
        _hook_that_waits(started, stopped), _start_context(), timeout=0.2
    )

    assert result.success is False
    assert result.exit_code == 124
    assert await asyncio.to_thread(stopped.wait, 5)
    executor.shutdown()


@pytest.mark.asyncio
async def test_cancelling_the_caller_cancels_the_hook():
    executor = ThreadPoolHookExecutor(default_timeout=60)
    executor.start()
    started, stopped = threading.Event(), threading.Event()
    call = asyncio.ensure_future(
        executor.execute_hook(_hook_that_waits(started, stopped), _start_context())
    )
    assert await asyncio.to_thread(started.wait, 5)

    call.cancel()

    with pytest.raises(asyncio.CancelledError):
        await call
    assert await asyncio.to_thread(stopped.wait, 5)
    executor.shutdown()


@pytest.mark.asyncio
async def test_a_hook_cancelled_before_it_starts_never_runs():
    executor = ThreadPoolHookExecutor(max_workers=1, default_timeout=60)
    executor.start()
    release = threading.Event()
    ran = threading.Event()

    async def occupy(ctx):
        await asyncio.to_thread(release.wait, 5)
        return HookResult(success=True)

    async def queued(ctx):
        ran.set()
        return HookResult(success=True)

    busy = asyncio.ensure_future(executor.execute_hook(occupy, _start_context()))
    waiting = asyncio.ensure_future(executor.execute_hook(queued, _start_context()))
    await asyncio.sleep(0.1)  # both submitted; the only worker is busy

    waiting.cancel()
    release.set()
    await busy

    with pytest.raises(asyncio.CancelledError):
        await waiting
    executor.shutdown()
    assert not ran.is_set()


def test_executor_singleton():
    executor = get_hook_executor()
    assert executor is not None
    shutdown_hook_executor()
    # After shutdown, it's None internally
