"""Tests for background shell command execution.

Background processes are launched through the ``Shell`` tool with
``background=True``; the registry and ``MonitorProcess`` collect them.
"""

import asyncio
import os
import re

import pytest
import pytest_asyncio

from zrb.config.config import CFG
from zrb.llm.permission import Capability, tool_capability
from zrb.llm.tool.ambient_state import current_chat_session_id
from zrb.llm.tool.shell import run_shell_command
from zrb.llm.tool.shell_background import (
    create_monitor_process_tool,
    get_shell_background_registry,
)
from zrb.util.contextvar_scope import scoped


@pytest_asyncio.fixture(autouse=True)
async def clean_registry():
    yield
    await get_shell_background_registry().cancel_all()


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
async def test_monitor_process_kill_unknown_handle_has_suggestion():
    # Regression: kill() on an unknown handle used to omit the recovery hint
    # that poll() gives for the identical condition.
    monitor = create_monitor_process_tool()
    result = await monitor("nonexistent-handle", kill=True)
    assert "Unknown handle" in result
    assert "[SYSTEM SUGGESTION]" in result


@pytest.mark.asyncio
async def test_cancel_all_clears(tmp_path):
    handle = await _start_bg("sleep 30", "", str(tmp_path))
    await get_shell_background_registry().cancel_all()
    monitor = create_monitor_process_tool()
    result = await monitor(handle)
    assert "Unknown handle" in result


@pytest.mark.asyncio
async def test_cancel_for_session_only_kills_that_sessions_processes(tmp_path):
    """A web chat session ending must not touch another session's still-
    running background process (unlike `cancel_all`, which is only safe when
    every session is ending at once). Tagged by the unique
    `current_chat_session_id`, never a display name."""
    with scoped(current_chat_session_id, "session-a-id"):
        handle_a = await _start_bg("sleep 30", "a", str(tmp_path))
    with scoped(current_chat_session_id, "session-b-id"):
        handle_b = await _start_bg("sleep 30", "b", str(tmp_path))

    await get_shell_background_registry().cancel_for_session("session-a-id")

    monitor = create_monitor_process_tool()
    result_a = await monitor(handle_a)
    assert "Unknown handle" in result_a
    result_b = await monitor(handle_b, wait=0.2)
    assert "running" in result_b
    await monitor(handle_b, kill=True)


@pytest.mark.asyncio
async def test_force_kill_all_kills_real_process(tmp_path):
    """`force_kill_all` is the atexit backstop — it must actually terminate
    the OS process, not just forget it in the registry. Reads the real OS pid
    back from a file the process writes itself, rather than reaching into the
    registry's internals."""
    pid_file = tmp_path / "pid"
    await _start_bg(f"echo $$ > {pid_file}; sleep 30", "pidwriter", str(tmp_path))
    for _ in range(50):
        if pid_file.exists() and pid_file.read_text().strip():
            break
        await asyncio.sleep(0.1)
    pid = int(pid_file.read_text().strip())

    get_shell_background_registry().force_kill_all()
    await asyncio.sleep(0.5)

    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def _extract_spill_path(poll_result: str, stream: str) -> str | None:
    """Pull the path out of a "full {stream} saved to <path>" message.

    ``rstrip(".")`` because the sentence's own trailing period sits right
    against the path with no separating whitespace.
    """
    match = re.search(rf"full {stream} saved to (\S+)", poll_result)
    if match is None:
        return None
    return match.group(1).rstrip(".")


@pytest.mark.asyncio
async def test_poll_truncates_large_output_and_reports_recoverable_path(
    tmp_path, monkeypatch
):
    # ADR-0059: a background process's output is now bounded — but the
    # elided head must stay recoverable via a spill file, not just dropped.
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 20)
    handle = await _start_bg(
        "head -c 500 /dev/zero | tr '\\0' 'A'", "flood", str(tmp_path)
    )
    monitor = create_monitor_process_tool()
    result = await monitor(handle, wait=5)

    assert "[SYSTEM SUGGESTION]" in result
    spill_path = _extract_spill_path(result, "stdout")
    assert spill_path is not None

    with open(spill_path, "r", encoding="utf-8") as f:
        full_output = f.read()
    assert full_output.count("A") == 500


async def _poll_until(registry, handle: str, needle: str, timeout: float = 10.0) -> str:
    """Poll until *needle* shows up in the response, and return that response.

    Polling is the only way to observe a background process, and it is not
    itself a wall-clock wait: `poll` consumes nothing while the process is
    still running, so retrying is free.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    result = ""
    while asyncio.get_running_loop().time() < deadline:
        result = registry.poll(handle)
        if needle in result:
            return result
        await asyncio.sleep(0.02)
    raise AssertionError(f"{needle!r} never appeared; last poll was:\n{result}")


@pytest.mark.asyncio
async def test_poll_reuses_same_spill_path_across_polls(tmp_path, monkeypatch):
    # Regression guard: a naive per-poll dump (mirroring shell.py's
    # foreground _dump_full_output) would leak a new temp file every call.
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 10)
    # Two floods separated by a gate the test opens, then a sleep that outlives
    # the test. Both details are load-bearing: `poll` *consumes* the handle once
    # the process has exited and drained, so a command that can finish before
    # either poll turns that poll's successor into "Unknown handle"; and gating
    # the second flood on a file (rather than a `sleep`) is what makes "output
    # grew between the two polls" a fact instead of a race.
    gate = tmp_path / "gate"
    command = (
        "head -c 50 /dev/zero | tr '\\0' 'X'; echo; "
        f"while [ ! -f {gate} ]; do sleep 0.02; done; "
        "head -c 50 /dev/zero | tr '\\0' 'Y'; echo; "
        "sleep 30"
    )
    handle = await _start_bg(command, "chunked", str(tmp_path))
    registry = get_shell_background_registry()

    try:
        first = await _poll_until(registry, handle, "X")
        first_path = _extract_spill_path(first, "stdout")
        assert first_path is not None

        # Let the second flood through: a per-poll dump would have had every
        # reason to open a fresh file for the grown output.
        gate.touch()
        second = await _poll_until(registry, handle, "Y")

        assert _extract_spill_path(second, "stdout") == first_path
    finally:
        await registry.cancel_all()


@pytest.mark.asyncio
async def test_spill_file_survives_after_handle_consumed(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 10)
    handle = await _start_bg(
        "echo 'this line is definitely longer than the tiny cap'",
        "flood",
        str(tmp_path),
    )
    monitor = create_monitor_process_tool()
    result = await monitor(handle, wait=5)

    assert "consumed" in result
    spill_path = _extract_spill_path(result, "stdout")
    assert spill_path is not None
    assert os.path.exists(spill_path)

    # The handle was consumed by the poll above (release uses close(), never
    # discard()) — a further poll must still report it as unknown, unchanged.
    result2 = await monitor(handle)
    assert "Unknown handle" in result2


@pytest.mark.asyncio
async def test_small_output_is_not_flagged_truncated(tmp_path):
    handle = await _start_bg("echo hello", "greeting", str(tmp_path))
    monitor = create_monitor_process_tool()
    result = await monitor(handle, wait=5)
    assert "[SYSTEM SUGGESTION]" not in result


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

    await get_shell_background_registry().cancel_all()
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
