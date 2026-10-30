"""An interrupting message ends a monitoring wait instead of holding the turn.

A `MonitorProcess(wait=N)` or `GetDelegationResult(wait=N)` call is a wait, not
work: nothing is cancelled by stopping it, so a send-now (or any message that
needs the turn) ends the wait and the call says so — the process or sub-agent
keeps running, and the same call waits for it again after the message is read.
"""

import asyncio

import pytest

from zrb.llm.shell_cut import (
    ShellCutSignal,
    current_shell_cut_signal,
    interrupted_notice,
    wait_unless_cut,
)
from zrb.llm.tool.delegate_background import _BackgroundRegistry


async def _finish_soon(task: asyncio.Task, seconds: float = 0.01) -> None:
    await asyncio.sleep(seconds)
    if not task.done():
        task.cancel()


async def _cut_soon(signal: ShellCutSignal, seconds: float = 0.01) -> None:
    await asyncio.sleep(seconds)
    signal.cut()


@pytest.mark.asyncio
async def test_a_wait_that_finishes_first_is_not_interrupted():
    done = asyncio.ensure_future(asyncio.sleep(0))

    interrupted = await wait_unless_cut({done}, seconds=5)

    assert interrupted is False


@pytest.mark.asyncio
async def test_a_cut_ends_the_wait_and_says_so():
    signal = ShellCutSignal()
    current_shell_cut_signal.set(signal)
    pending = asyncio.ensure_future(asyncio.sleep(30))
    asyncio.ensure_future(_cut_soon(signal))

    interrupted = await wait_unless_cut({pending}, seconds=5)

    assert interrupted is True
    # Nothing was cancelled: the work the wait was watching is still there.
    assert not pending.done()
    await _finish_soon(pending)


@pytest.mark.asyncio
async def test_without_a_run_there_is_no_cut_to_hear():
    pending = asyncio.ensure_future(asyncio.sleep(30))
    asyncio.ensure_future(_finish_soon(pending))

    interrupted = await wait_unless_cut({pending}, seconds=5)

    assert interrupted is False


def test_the_notice_names_the_call_that_picks_the_wait_up():
    notice = interrupted_notice("MonitorProcess(handle='sly-one', wait=N)")

    assert notice.startswith("[interrupted]")
    assert "MonitorProcess(handle='sly-one', wait=N)" in notice
    # The work is still running; a retry that starts it again would be a second
    # copy, which is the failure the notice exists to prevent.
    assert "second copy" in notice
    assert "still running" in notice


@pytest.mark.asyncio
async def test_a_collect_that_is_cut_reports_the_wait_interrupted():
    registry = _BackgroundRegistry()
    signal = ShellCutSignal()
    current_shell_cut_signal.set(signal)
    task = asyncio.ensure_future(asyncio.sleep(30))
    registry._tasks["bg-1"] = task
    registry.poll = lambda handle: "Status: running"
    asyncio.ensure_future(_cut_soon(signal))

    report = await registry.collect("bg-1", wait=5)

    assert report.startswith("[interrupted]")
    assert "GetDelegationResult(handle='bg-1')" in report
    assert "Status: running" in report
    assert not task.done()
    await _finish_soon(task)
