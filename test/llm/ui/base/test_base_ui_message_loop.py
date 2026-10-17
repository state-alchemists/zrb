"""BaseUI's message loop: quitting ends it whatever the running job does."""

import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.ui.base.message_queue import QueuedMessage
from zrb.llm.ui.base.ui import BaseUI


class ConcreteUI(BaseUI):
    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        pass

    async def ask_user(self, prompt: str) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0

    async def run_async(self) -> str:
        return ""


@pytest.fixture
def ui():
    ctx = Context(SharedContext(), "test", 0, "")
    llm_task = MagicMock(hook_manager=None, active_hook_manager=None)
    return ConcreteUI(ctx=ctx, llm_task=llm_task, history_manager=MagicMock())


def _job(run) -> QueuedMessage:
    return QueuedMessage(text="hi", attachments=[], kind="message", run=run)


async def _absorbs_its_cancel(started: asyncio.Event) -> None:
    """A turn that handles Ctrl+C itself and returns normally."""
    started.set()
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        return


async def _until_running(ui: BaseUI, started: asyncio.Event) -> asyncio.Task:
    loop = asyncio.create_task(ui.process_messages_loop())
    await asyncio.wait_for(started.wait(), 1)
    return loop


async def _is_ended(task: asyncio.Task) -> bool:
    """Whether *task* ends within a second. Unlike `wait_for`, a task still
    running is not cancelled, which would end the loop by itself."""
    await asyncio.wait({task}, timeout=1)
    return task.done()


async def _is_queue_settled(ui: BaseUI) -> bool:
    """Whether every entry taken off the queue was marked done."""
    join = asyncio.ensure_future(ui.effective_message_queue.join())
    await asyncio.wait({join}, timeout=1)
    join.cancel()
    return join.done() and not join.cancelled()


async def _stop(*tasks: asyncio.Task) -> None:
    """Leave no task running, even one ignoring a cancel."""
    for _ in range(3):
        for task in tasks:
            task.cancel()
        await asyncio.wait(set(tasks), timeout=0.2)


@pytest.mark.asyncio
async def test_quitting_ends_the_loop_when_the_job_absorbs_its_cancel(ui):
    started = asyncio.Event()
    ui.effective_message_queue.put_nowait(_job(lambda: _absorbs_its_cancel(started)))
    loop = await _until_running(ui, started)

    loop.cancel()
    is_ended = await _is_ended(loop)
    is_settled = await _is_queue_settled(ui)
    await _stop(loop)

    assert is_ended
    assert is_settled


@pytest.mark.asyncio
async def test_cancelling_only_the_job_keeps_the_loop_running(ui):
    started, second_ran = asyncio.Event(), asyncio.Event()

    async def second() -> None:
        second_ran.set()

    ui.effective_message_queue.put_nowait(_job(lambda: _absorbs_its_cancel(started)))
    ui.effective_message_queue.put_nowait(_job(second))
    loop = await _until_running(ui, started)

    ui.running_llm_task.cancel()
    await asyncio.wait_for(second_ran.wait(), 1)
    is_running = not loop.done()
    await _stop(loop)

    assert is_running


@pytest.mark.asyncio
async def test_quitting_again_ends_the_loop_while_the_job_ignores_its_cancel(ui):
    started = asyncio.Event()

    async def ignores_its_cancel() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.Event().wait()

    ui.effective_message_queue.put_nowait(_job(ignores_its_cancel))
    loop = await _until_running(ui, started)
    job = ui.running_llm_task

    loop.cancel()
    await asyncio.sleep(0.05)
    loop.cancel()
    is_ended = await _is_ended(loop)
    is_settled = await _is_queue_settled(ui)
    await _stop(loop, job)

    assert is_ended
    assert is_settled
