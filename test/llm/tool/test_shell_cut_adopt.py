"""Ctrl+G moves the command that is in the way, so the message lands now.

A steered message is read at the next model request, and the next request comes
after the running tool returns. A long command therefore holds the turn hostage:
these tests pin the way out — the command steps aside the same way its own
timeout makes it step aside, and the tool call returns while it keeps running.
"""

import asyncio
import re
import shlex
import sys
from pathlib import Path

import pytest

from zrb.llm.shell_cut import ShellCutSignal, current_shell_cut_signal
from zrb.llm.tool.shell import run_shell_command
from zrb.llm.tool.shell_background import get_shell_background_registry

_PYTHON = shlex.quote(Path(sys.executable).as_posix())


def _ticker_command(tmp_path, seconds: float = 30.0) -> str:
    script = tmp_path / "ticker.py"
    script.write_text(
        "import time\n"
        f"deadline = time.monotonic() + {seconds}\n"
        "index = 0\n"
        "while time.monotonic() < deadline:\n"
        "    print('TICK', index, flush=True)\n"
        "    index += 1\n"
        "    time.sleep(0.1)\n",
        encoding="utf-8",
    )
    return f"{_PYTHON} {shlex.quote(script.as_posix())}"


def _handle(text: str) -> str:
    match = re.search(r"Handle: (\S+)", text)
    assert match is not None, text
    return match.group(1)


def _highest_tick(text: str) -> int:
    ticks = [int(index) for index in re.findall(r"TICK (\d+)", text)]
    assert ticks, text
    return max(ticks)


@pytest.mark.asyncio
async def test_a_cut_moves_the_running_command_to_the_background(tmp_path):
    signal = ShellCutSignal()
    token = current_shell_cut_signal.set(signal)
    try:
        running = asyncio.ensure_future(
            run_shell_command(_ticker_command(tmp_path), timeout=60)
        )
        await asyncio.sleep(0.5)
        signal.cut()
        result = await asyncio.wait_for(running, 10)
    finally:
        current_shell_cut_signal.reset(token)

    handle = _handle(result)
    try:
        assert "NOT killed" in result
        assert f"MonitorProcess(handle='{handle}')" in result
        before = _highest_tick(result)
        await asyncio.sleep(0.5)
        status = await get_shell_background_registry().collect(handle)

        assert "Status: running" in status
        assert _highest_tick(status) > before, "the work stopped when it moved"
    finally:
        await get_shell_background_registry().kill(handle)


@pytest.mark.asyncio
async def test_the_report_says_the_turn_needs_the_command_out_of_the_way(tmp_path):
    signal = ShellCutSignal()
    token = current_shell_cut_signal.set(signal)
    try:
        running = asyncio.ensure_future(
            run_shell_command(_ticker_command(tmp_path), timeout=60)
        )
        await asyncio.sleep(0.4)
        signal.cut()
        result = await asyncio.wait_for(running, 10)
    finally:
        current_shell_cut_signal.reset(token)

    try:
        assert "handle" in result
        assert "message" in result, "the model is not told why it was moved"
        assert "Do not run the command again" in result
        # The timeout has not elapsed, so its wording would be a lie.
        assert "did not finish within" not in result
    finally:
        await get_shell_background_registry().kill(_handle(result))


@pytest.mark.asyncio
async def test_a_cut_leaves_a_deliberate_wait_alone(tmp_path):
    """`sleep` is a delay the caller wrote on purpose: there is nothing to move
    it aside for, and killing it would throw the wait away."""
    signal = ShellCutSignal()
    token = current_shell_cut_signal.set(signal)
    try:
        running = asyncio.ensure_future(run_shell_command("sleep 1.2", timeout=60))
        await asyncio.sleep(0.3)
        signal.cut()
        result = await asyncio.wait_for(running, 20)
    finally:
        current_shell_cut_signal.reset(token)

    assert "Handle:" not in result
    assert "0" in result


@pytest.mark.asyncio
async def test_a_cut_from_before_the_call_does_not_move_it(tmp_path):
    """The key was pressed during an earlier tool call; this command was not
    running then and must be left alone."""
    signal = ShellCutSignal()
    signal.cut()
    token = current_shell_cut_signal.set(signal)
    try:
        result = await run_shell_command("sleep 0.3", timeout=60)
    finally:
        current_shell_cut_signal.reset(token)

    assert "Handle:" not in result


@pytest.mark.asyncio
async def test_no_signal_leaves_the_timeout_alone(tmp_path):
    """Outside a run there is nobody to cut in: the timeout still decides."""
    result = await run_shell_command(_ticker_command(tmp_path, seconds=10), timeout=1)
    handle = _handle(result)
    try:
        assert "did not finish within 1s" in result
    finally:
        await get_shell_background_registry().kill(handle)
