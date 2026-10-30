"""An interrupting message ends a monitoring wait instead of holding the turn.

A `MonitorProcess(wait=N)` or `GetDelegationResult(wait=N)` call is a wait, not
work: nothing is cancelled by stopping it, so a send-now (or any message that
needs the turn) ends the wait and the call says so — the process or sub-agent
keeps running, and the same call waits for it again after the message is read.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.llm.shell_cut import (
    ShellCutSignal,
    current_shell_cut_signal,
    interrupted_notice,
    is_cut_while_waiting,
)
from zrb.llm.tool.delegate_background import _BackgroundRegistry
from zrb.llm.ui.buffered_ui import BufferedUI


async def _finish_soon(task: asyncio.Task, seconds: float = 0.01) -> None:
    await asyncio.sleep(seconds)
    if not task.done():
        task.cancel()


async def _cut_soon(signal: ShellCutSignal, seconds: float = 0.01) -> None:
    await asyncio.sleep(seconds)
    signal.cut()


class _CutThatSettlesTheWork(ShellCutSignal):
    """A cut that lands as the work finishes.

    Both complete together: the keypress arrives, and the sub-agent or process
    is done by the time the wait reports. A notice telling the model to wait on
    the same handle again would point at a handle `poll` has just consumed.
    """

    def __init__(self, settle) -> None:
        super().__init__()
        self._settle = settle

    async def wait_for_cut(self, generation: int) -> None:
        self._settle()


@pytest.mark.asyncio
async def test_a_wait_that_finishes_first_is_not_interrupted():
    done = asyncio.ensure_future(asyncio.sleep(0))

    interrupted = await is_cut_while_waiting({done}, seconds=5)

    assert interrupted is False


@pytest.mark.asyncio
async def test_a_cut_ends_the_wait_and_says_so():
    signal = ShellCutSignal()
    current_shell_cut_signal.set(signal)
    pending = asyncio.ensure_future(asyncio.sleep(30))
    asyncio.ensure_future(_cut_soon(signal))

    interrupted = await is_cut_while_waiting({pending}, seconds=5)

    assert interrupted is True
    # Nothing was cancelled: the work the wait was watching is still there.
    assert not pending.done()
    await _finish_soon(pending)


@pytest.mark.asyncio
async def test_without_a_run_there_is_no_cut_to_hear():
    pending = asyncio.ensure_future(asyncio.sleep(30))
    asyncio.ensure_future(_finish_soon(pending))

    interrupted = await is_cut_while_waiting({pending}, seconds=5)

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
async def test_a_cut_leaves_no_task_of_its_own_behind():
    """The wait reaps the tasks it started before it reports.

    A cancelled `asyncio.wait` left pending until the loop's next turn keeps the
    watched work's done-callbacks registered, and a loop that closes in between
    reports it as a task destroyed while pending.
    """
    signal = ShellCutSignal()
    current_shell_cut_signal.set(signal)
    pending = asyncio.ensure_future(asyncio.sleep(30))
    asyncio.get_running_loop().call_later(0.01, signal.cut)

    interrupted = await is_cut_while_waiting({pending}, seconds=5)

    assert interrupted is True
    assert not pending.done()
    # The only tasks alive are the test's own: the work being watched, and the
    # test. Anything else is a task the wait started and did not reap.
    ours = {asyncio.current_task(), pending}
    assert asyncio.all_tasks() - ours == set()
    await _finish_soon(pending)


@pytest.mark.asyncio
async def test_a_cut_that_lands_with_the_finished_work_reports_the_result():
    """A finished handle is collected, not reported interrupted.

    `poll` consumes a finished handle, so an interruption notice over a task
    that settled with the cut would send the model to a handle that is gone.
    """
    registry = _BackgroundRegistry()
    task = asyncio.ensure_future(asyncio.sleep(30))
    registry.adopt("bg-1", "agent", task, BufferedUI(MagicMock()))
    registry.poll = lambda handle: "Status: finished"
    current_shell_cut_signal.set(_CutThatSettlesTheWork(task.cancel))

    report = await registry.collect("bg-1", wait=5)

    assert not report.startswith("[interrupted]")
    assert "Status: finished" in report
    assert "wait=N" not in report


@pytest.mark.asyncio
async def test_a_collect_that_is_cut_reports_the_wait_interrupted():
    registry = _BackgroundRegistry()
    signal = ShellCutSignal()
    current_shell_cut_signal.set(signal)
    task = asyncio.ensure_future(asyncio.sleep(30))
    registry.adopt("bg-1", "agent", task, BufferedUI(MagicMock()))
    registry.poll = lambda handle: "Status: running"
    asyncio.ensure_future(_cut_soon(signal))

    report = await registry.collect("bg-1", wait=5)

    assert report.startswith("[interrupted]")
    # The retry must carry a wait: `GetDelegationResult(handle)` alone defaults
    # to wait=0, so it would come back "still running" the instant it is called.
    assert "GetDelegationResult(handle='bg-1', wait=N)" in report
    assert "Status: running" in report
    assert not task.done()
    await _finish_soon(task)
