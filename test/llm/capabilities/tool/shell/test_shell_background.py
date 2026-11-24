"""Tests for background shell execution."""

import asyncio
import os
import re

import pytest
import pytest_asyncio

from zrb.config.config import CFG
from zrb.llm.capabilities.permission import Capability, tool_capability
from zrb.llm.capabilities.tool.shell import run_shell_command
from zrb.llm.capabilities.tool.shell.background import (
    create_monitor_process_tool,
    get_shell_background_registry,
)
from zrb.llm.contracts.shared.ambient_state import current_chat_session_id
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
    """Cancelling one session leaves another session's process running."""
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
async def test_a_web_session_cannot_read_or_kill_anothers_handle(tmp_path):
    """A handle belongs to the web chat session that started it.

    `summary` and `cancel_for_session` already honored the owner; `poll`,
    `collect` and `kill` let any session read or kill another session's
    process by naming its handle.
    """
    with scoped(current_chat_session_id, "session-a-id"):
        handle = await _start_bg("sleep 30", "a", str(tmp_path))
        registry = get_shell_background_registry()
        assert "running" in registry.poll(handle)

    monitor = create_monitor_process_tool()
    with scoped(current_chat_session_id, "session-b-id"):
        assert "Unknown handle" in registry.poll(handle)
        assert "Unknown handle" in await monitor(handle)
        assert "Unknown handle" in await monitor(handle, wait=0.2)
        assert "Unknown handle" in await monitor(handle, kill=True)

    # The refused kill left the owner's process alone.
    with scoped(current_chat_session_id, "session-a-id"):
        assert "running" in registry.poll(handle)
        assert "Killed" in await monitor(handle, kill=True)


@pytest.mark.asyncio
async def test_a_handle_started_outside_a_web_session_stays_reachable(tmp_path):
    """A CLI start has an empty owner, and an empty owner is never foreign."""
    handle = await _start_bg("sleep 30", "cli", str(tmp_path))
    registry = get_shell_background_registry()

    with scoped(current_chat_session_id, "session-b-id"):
        assert "running" in registry.poll(handle)
        assert "Killed" in await create_monitor_process_tool()(handle, kill=True)


@pytest.mark.asyncio
async def test_a_web_handle_stays_reachable_without_a_current_session(tmp_path):
    """Only two differing non-empty ids are refused; an empty caller id is not."""
    with scoped(current_chat_session_id, "session-a-id"):
        handle = await _start_bg("sleep 30", "a", str(tmp_path))
    registry = get_shell_background_registry()

    assert "running" in registry.poll(handle)
    assert "Killed" in await create_monitor_process_tool()(handle, kill=True)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix",
    reason="`$$` under a Windows POSIX shell is an MSYS pid, not an OS one",
)
async def test_force_kill_all_kills_real_process(tmp_path):
    """The atexit backstop terminates the real process on POSIX."""
    pid_file = tmp_path / "pid"
    # `pid_file.as_posix()`, not str(): backslashes are escape characters to
    # the shell, and a POSIX shell on Windows accepts "C:/...".
    await _start_bg(
        f"echo $$ > {pid_file.as_posix()}; sleep 30", "pidwriter", str(tmp_path)
    )
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
    """Extract a spill path from a poll response."""
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
    """Poll until a response contains ``needle``."""
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
        f"while [ ! -f {gate.as_posix()} ]; do sleep 0.02; done; "
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
async def test_a_long_single_line_is_read_with_the_foreground_limit(tmp_path):
    """A 1MB line sits between asyncio's default 64KB limit and the 8MB the
    foreground allows; the background reader must capture it, not die on it."""
    handle = await _start_bg(
        "head -c 1000000 /dev/zero | tr '\\0' 'A'", "flood", str(tmp_path)
    )
    result = await create_monitor_process_tool()(handle, wait=10)

    assert "1000000 chars total" in result
    assert "pipe read limit" not in result


@pytest.mark.asyncio
async def test_a_line_over_the_pipe_limit_is_reported_as_truncation(
    tmp_path, monkeypatch
):
    """When even the 8MB ceiling is outrun, the reader says so and ends cleanly
    instead of dying with an unretrieved ValueError."""
    from zrb.llm.capabilities.tool.shell import background

    monkeypatch.setattr(background, "_PIPE_LIMIT", 1024)
    handle = await _start_bg(
        "head -c 4096 /dev/zero | tr '\\0' 'A'", "flood", str(tmp_path)
    )
    result = await _poll_until(
        get_shell_background_registry(), handle, "pipe read limit"
    )

    assert "stdout truncated" in result


@pytest.mark.asyncio
async def test_an_over_limit_line_is_drained_so_the_child_can_exit(
    tmp_path, monkeypatch
):
    """Stopping at readline's ValueError leaves the child blocked on a full
    pipe, so it never exits and `MonitorProcess(wait)` never returns. The rest
    of the stream must be read in bounded chunks until EOF instead."""
    from zrb.llm.capabilities.tool.shell import background

    monkeypatch.setattr(background, "_PIPE_LIMIT", 1024)
    handle = await _start_bg(
        "head -c 1048576 /dev/zero | tr '\\0' 'A'; echo; echo DONE",
        "flood",
        str(tmp_path),
    )
    result = await create_monitor_process_tool()(handle, wait=10)

    assert "exited (code 0)" in result
    assert "DONE" in result
    assert "stdout truncated" in result


@pytest.mark.asyncio
async def test_an_over_limit_stderr_line_is_drained_too(tmp_path, monkeypatch):
    """The stderr reader drains an over-limit line the same way stdout's does."""
    from zrb.llm.capabilities.tool.shell import background

    monkeypatch.setattr(background, "_PIPE_LIMIT", 1024)
    handle = await _start_bg(
        "head -c 1048576 /dev/zero | tr '\\0' 'B' 1>&2; echo 1>&2; "
        "echo STDERR-DONE 1>&2",
        "flood",
        str(tmp_path),
    )
    result = await create_monitor_process_tool()(handle, wait=10)

    assert "exited (code 0)" in result
    assert "STDERR-DONE" in result
    assert "stderr truncated" in result


@pytest.mark.asyncio
async def test_a_multibyte_character_split_across_chunks_is_decoded_once(
    tmp_path, monkeypatch
):
    """The drain reads bytes, and a UTF-8 character can straddle two chunks.
    Decoding each chunk on its own would turn one character into two
    replacement marks."""
    import shlex
    import sys
    from pathlib import Path

    from zrb.llm.capabilities.tool.shell import background

    monkeypatch.setattr(background, "_PIPE_LIMIT", 16)
    monkeypatch.setattr(background, "_DRAIN_CHUNK_SIZE", 1)
    script = tmp_path / "flood.py"
    # The multibyte characters are written after readline's own buffered
    # discard, so the drain is what decodes them.
    script.write_text(
        "import sys, time\n"
        "sys.stdout.buffer.write(b'A' * 40)\n"
        "sys.stdout.buffer.flush()\n"
        "time.sleep(0.2)\n"
        "sys.stdout.buffer.write("
        "'\\u00e9'.encode('utf-8') * 4 + b'\\nDONE\\n')\n",
        encoding="utf-8",
    )
    command = (
        f"{shlex.quote(Path(sys.executable).as_posix())} "
        f"{shlex.quote(script.as_posix())}"
    )
    handle = await _start_bg(command, "flood", str(tmp_path))
    result = await create_monitor_process_tool()(handle, wait=10)

    assert "exited (code 0)" in result
    assert "éééé" in result
    assert "\ufffd" not in result


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
async def test_poll_reports_a_capped_spill_file(tmp_path, monkeypatch):
    """A background run has no deadline, so the spill file stops at its cap and
    the poll says the on-disk copy is not the whole stream."""
    from zrb.llm.capabilities.tool.shell import capture

    monkeypatch.setattr(capture, "SPILL_MAX_CHARS", 50)
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 10)
    handle = await _start_bg(
        "head -c 500 /dev/zero | tr '\\0' 'A'", "flood", str(tmp_path)
    )
    result = await create_monitor_process_tool()(handle, wait=5)

    assert "spill file was capped" in result
    assert "saved up to 50 chars" in result


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
