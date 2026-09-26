import asyncio
import contextvars
import threading
import time

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
    assert stopped.is_set()  # stopped before the caller got its result
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
    assert stopped.is_set()  # stopped before the cancellation reached the caller
    executor.shutdown()


@pytest.mark.asyncio
async def test_a_hook_cancellation_cannot_reach_holds_its_caller_only_briefly():
    executor = ThreadPoolHookExecutor(default_timeout=60, cancel_grace_seconds=0.2)
    executor.start()
    release = threading.Event()

    async def blocked(ctx):
        release.wait(5)  # a synchronous call: its loop never sees the cancel
        return HookResult(success=True)

    started = time.monotonic()
    result = await executor.execute_hook(blocked, _start_context(), timeout=0.1)
    elapsed = time.monotonic() - started

    assert result.exit_code == 124
    assert elapsed < 2
    release.set()
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


@pytest.mark.asyncio
async def test_a_hook_runs_in_the_callers_context():
    """A pool thread starts with an empty context: without the copy, a hook
    sees none of the caller's ambient state — the run's model, its tool call."""
    executor = ThreadPoolHookExecutor()
    executor.start()
    ambient: contextvars.ContextVar[str] = contextvars.ContextVar("ambient")
    seen: list[str | None] = []

    async def reads_the_caller_context(ctx):
        seen.append(ambient.get("unset"))
        return HookResult(success=True)

    token = ambient.set("the run's model")
    try:
        result = await executor.execute_hook(reads_the_caller_context, _start_context())
    finally:
        ambient.reset(token)
        executor.shutdown()

    assert result.success is True
    assert seen == ["the run's model"]


@pytest.mark.asyncio
async def test_a_hook_does_not_inherit_what_is_bound_to_the_callers_loop():
    """The hook runs in an event loop of its own, so the chat's UI, tool
    confirmation and approval channel — all driven from the caller's loop —
    are not passed on, while the rest of the caller's state is."""
    from zrb.llm.agent_state import current_model, current_ui
    from zrb.llm.approval.approval_channel import current_approval_channel

    executor = ThreadPoolHookExecutor()
    executor.start()
    seen: dict = {}

    async def reads_the_caller_context(ctx):
        seen.update(
            ui=current_ui.get(),
            channel=current_approval_channel.get(),
            model=current_model.get(),
        )
        return HookResult(success=True)

    ui = object()
    tokens = [
        (current_ui, current_ui.set(ui)),
        (current_approval_channel, current_approval_channel.set(object())),
        (current_model, current_model.set("the run's model")),
    ]
    try:
        await executor.execute_hook(reads_the_caller_context, _start_context())
        callers_ui = current_ui.get()
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
        executor.shutdown()

    assert seen == {"ui": None, "channel": None, "model": "the run's model"}
    # The caller's own binding is untouched.
    assert callers_ui is ui


def test_executor_singleton():
    executor = get_hook_executor()
    assert executor is not None
    shutdown_hook_executor()
    # After shutdown, it's None internally
