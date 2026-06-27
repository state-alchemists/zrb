"""Tests for background shell command execution.

Background processes are launched through the public ``Shell``/``Bash`` tools
with ``background=True``; the registry and ``MonitorProcess`` collect them.
"""

import asyncio

import pytest

from zrb.llm.permission import Capability, tool_capability
from zrb.llm.tool.shell import run_shell_command
from zrb.llm.tool.shell_background import (
    create_monitor_process_tool,
    get_shell_background_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    get_shell_background_registry().cancel_all()


async def _start_bg(command: str, description: str = "", cwd: str = "") -> str:
    """Start a background command via the public tool and return its handle."""
    msg = await run_shell_command(
        command, background=True, description=description, cwd=cwd
    )
    assert "Handle:" in msg
    return msg.split("Handle:")[1].split(".")[0].strip()


def test_capabilities():
    assert tool_capability(create_monitor_process_tool()) == Capability.EXECUTE


def test_tool_names():
    assert create_monitor_process_tool().__name__ == "MonitorProcess"


@pytest.mark.asyncio
async def test_shell_background_returns_handle(tmp_path):
    handle = await _start_bg("echo hello", "greeting", str(tmp_path))
    registry = get_shell_background_registry()
    await asyncio.sleep(0.5)
    result = registry.poll(handle)
    assert "hello" in result or "exited" in result or "running" in result


@pytest.mark.asyncio
async def test_monitor_process_unknown():
    tool = create_monitor_process_tool()
    msg = await tool("nonexistent-handle")
    assert "Unknown handle" in msg


@pytest.mark.asyncio
async def test_monitor_process_wait_returns_on_exit(tmp_path):
    # A quick command + a generous wait returns the instant it exits — well
    # before the timeout — proving wait early-returns rather than sleeping.
    handle = await _start_bg("echo done", "quick", str(tmp_path))
    monitor = create_monitor_process_tool()
    result = await monitor(handle, wait=5)
    assert "exited" in result
    assert "done" in result


@pytest.mark.asyncio
async def test_monitor_process_wait_times_out_while_running(tmp_path):
    # A long command with a short wait falls through to the running status; the
    # process keeps running (not killed) so we can still kill it explicitly.
    handle = await _start_bg("sleep 30", "sleeper", str(tmp_path))
    monitor = create_monitor_process_tool()
    result = await monitor(handle, wait=0.2)
    assert "running" in result
    await monitor(handle, kill=True)


@pytest.mark.asyncio
async def test_monitor_process_kill(tmp_path):
    handle = await _start_bg("sleep 30", "sleeper", str(tmp_path))
    monitor = create_monitor_process_tool()
    result = await monitor(handle, kill=True)
    assert "Killed" in result
    # Poll again — handle is consumed after kill
    result2 = await monitor(handle)
    assert "Unknown handle" in result2


@pytest.mark.asyncio
async def test_cancel_all_clears(tmp_path):
    handle = await _start_bg("sleep 30", "", str(tmp_path))
    get_shell_background_registry().cancel_all()
    monitor = create_monitor_process_tool()
    result = await monitor(handle)
    assert "Unknown handle" in result


def _reader_task_count() -> int:
    # Count still-pending detached reader/wait tasks spawned by the registry.
    return sum(
        1
        for t in asyncio.all_tasks()
        if not t.done()
        and any(
            name in repr(t.get_coro())
            for name in ("_read_stdout", "_read_stderr", "_wait_exit")
        )
    )


@pytest.mark.asyncio
async def test_cancel_all_cancels_reader_tasks(tmp_path):
    # B27: cancel_all() must cancel the detached reader/wait tasks, not just
    # kill the process and leave them leaking.
    await _start_bg("sleep 30", "", str(tmp_path))
    await asyncio.sleep(0.1)
    assert _reader_task_count() > 0

    get_shell_background_registry().cancel_all()
    # Allow the event loop to process the cancellations.
    await asyncio.sleep(0.1)
    assert _reader_task_count() == 0


@pytest.mark.asyncio
async def test_kill_cancels_reader_tasks(tmp_path):
    # B27: kill() must also cancel the detached reader/wait tasks.
    handle = await _start_bg("sleep 30", "", str(tmp_path))
    await asyncio.sleep(0.1)
    assert _reader_task_count() > 0

    monitor = create_monitor_process_tool()
    await monitor(handle, kill=True)
    await asyncio.sleep(0.1)
    assert _reader_task_count() == 0
