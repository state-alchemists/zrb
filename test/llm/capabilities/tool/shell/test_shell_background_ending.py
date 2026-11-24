"""How a background command's ending is recorded, and how its time is stopped.

A background command is not always one process. ``server & echo started``
leaves a child holding the pipes after the shell itself is gone, so "the shell
exited" and "the work exited" are two different moments. The registry has to
record the first without waiting for the second: the exit code is what a
monitor, a kill and the session's wake-up all read, and it must not be held
back by a child that keeps writing. The deadline a timeout arms has the other
job — it must reach that child, even though the shell's exit code is on record
and the shell is no longer there to be signalled.
"""

import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio

from zrb.config.config import CFG
from zrb.llm.capabilities.tool.shell import run_shell_command
from zrb.llm.capabilities.tool.shell.background import (
    create_monitor_process_tool,
    get_shell_background_registry,
)
from zrb.llm.capabilities.tool.shell.capture import StreamCapture


@pytest_asyncio.fixture(autouse=True)
async def clean_registry():
    yield
    await get_shell_background_registry().cancel_all()


async def _start_bg(command: str, description: str = "") -> str:
    """Start a background command via the public tool and return its handle."""
    msg = await run_shell_command(command, background=True, description=description)
    assert "Handle:" in msg
    return msg.split("Handle:")[1].split(".")[0].strip()


@pytest.mark.asyncio
async def test_a_child_that_outlives_the_shell_still_records_the_exit_code():
    """The shell's exit code is the registry's to record, however long a child
    it left running keeps the pipes open.

    `Process.wait()` waits for those pipes as well, so a `cmd &` child holds the
    exit code back: the handle goes on saying "running" long after the shell has
    gone, a monitor waits out its whole allowance for an ending that already
    happened, and the session is never told.
    """
    handle = await _start_bg("sleep 5 & echo SPAWNED", "leaves a child")

    result = await create_monitor_process_tool()(handle, wait=2)

    assert "exited (code 0)" in result
    assert "SPAWNED" in result


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix",
    reason=(
        "a child that outlived its shell is only reachable through the group "
        "the shell led, and a process group is a POSIX idea"
    ),
)
async def test_an_adopted_daemon_is_stopped_at_its_deadline(tmp_path, monkeypatch):
    """The shell's own exit is not the end of the time in the background.

    An adopted command that leaves a child behind — `server & sleep 1` — exits
    while the child it started keeps working, and its exit code is now recorded
    at that moment. The deadline was armed to stop what the registry took on,
    so it must still reach that child, which only the shell's process group
    names once the shell itself is gone.
    """
    monkeypatch.setattr(CFG, "LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS", 2)
    registry = get_shell_background_registry()
    pid_file = tmp_path / "child.pid"
    process = await asyncio.create_subprocess_exec(
        "bash",
        "-c",
        f"sleep 30 & echo $! > {pid_file.as_posix()}; sleep 0.5",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    handle = await registry.adopt(
        process, "left a child behind", StreamCapture(1000, 0), StreamCapture(1000, 0)
    )

    child = await _child_pid(pid_file)
    assert not await _is_gone(child, 0.5), "the child died before its deadline"
    await asyncio.sleep(2.5)
    result = registry.poll(handle)

    assert "killed after 2s in the background" in result
    assert await _is_gone(child), "the child outlived the time it was given"


async def _child_pid(pid_file: Path) -> int:
    """The pid the adopted command wrote for the child it left running."""
    for _ in range(100):
        if pid_file.exists() and pid_file.read_text().strip():
            return int(pid_file.read_text().strip())
        await asyncio.sleep(0.05)
    raise AssertionError("the adopted command never named its child")


async def _is_gone(pid: int, seconds: float = 10.0) -> bool:
    """Whether *pid* stops existing within *seconds*: `os.kill` checks, no signal."""
    for _ in range(int(seconds / 0.05)):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        await asyncio.sleep(0.05)
    return False
