"""A command that outruns its timeout keeps running, under a handle.

The timeout used to kill the process, so everything it had already done was
lost and the model was told to run it again — a second copy of the work. It is
now moved to the background instead, and these tests hold that shape.
"""

import asyncio
import math
import re
import shlex
import sys
import time
from pathlib import Path

import pytest

from zrb.config.config import CFG
from zrb.llm.tool.shell import run_shell_command
from zrb.llm.tool.shell_background import get_shell_background_registry

_PYTHON = shlex.quote(Path(sys.executable).as_posix())

_MEASUREMENT_TIMEOUT_SECONDS = 60
_STARTUP_MARGIN_SECONDS = 1


async def _window_outlasting_startup() -> int:
    """A timeout that leaves the command room to start *and* to print.

    Two tests below need output from inside the window they give a command: a
    tick in the report, and an overflow spill file. Whether that output exists
    depends on how fast the machine boots an interpreter, and on a shared
    runner that is most of a one-second window. The bank's GitLab runner
    reported an empty stdout, and no spill file, for scripts that had not
    reached their first line yet, where GitHub's runner saw ticks and a spill
    from the same commit. So the window is measured against this machine
    instead of being assumed to be a second.
    """
    start = time.monotonic()
    await run_shell_command(
        f'{_PYTHON} -c "print(1)"', timeout=_MEASUREMENT_TIMEOUT_SECONDS
    )
    return math.ceil(time.monotonic() - start) + _STARTUP_MARGIN_SECONDS


def _ticker_command(tmp_path, seconds: float = 30.0) -> str:
    """A script that prints while it runs: nothing to wait for, just work."""
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


def _ticks(text: str) -> list[int]:
    return [int(index) for index in re.findall(r"TICK (\d+)", text)]


def _highest_tick(text: str) -> int:
    ticks = _ticks(text)
    assert ticks, text
    return max(ticks)


async def _collect_until_tick_past(
    handle: str, after: int, seconds: float = 6.0
) -> str:
    """Poll the handle until it reports a tick past *after*, or give up.

    Waiting a fixed sleep assumes the adopted command has already printed, which
    is the assumption that broke on the Windows runner: there the interpreter
    was still starting when the window closed, so the report held no output at
    all. What the report must not do is stop the output, so the test waits for
    the next tick instead of assuming one was due.
    """
    deadline = time.monotonic() + seconds
    status = await get_shell_background_registry().collect(handle)
    while time.monotonic() < deadline:
        if any(tick > after for tick in _ticks(status)):
            return status
        await asyncio.sleep(0.2)
        status = await get_shell_background_registry().collect(handle)
    return status


def _slow_starter_command(tmp_path, quiet_seconds: float = 3.0) -> str:
    """A command that says nothing for a while, then ticks: a slow interpreter."""
    script = tmp_path / "slow_ticker.py"
    script.write_text(
        "import time\n"
        f"time.sleep({quiet_seconds})\n"
        "index = 0\n"
        "while True:\n"
        "    print('TICK', index, flush=True)\n"
        "    index += 1\n"
        "    time.sleep(0.1)\n",
        encoding="utf-8",
    )
    return f"{_PYTHON} {shlex.quote(script.as_posix())}"


@pytest.mark.asyncio
async def test_a_timed_out_command_keeps_running_under_a_handle(tmp_path):
    window = await _window_outlasting_startup()
    result = await run_shell_command(_ticker_command(tmp_path), timeout=window)
    handle = _handle(result)
    try:
        assert f"(moved to background after {window}s)" in result
        assert "NOT killed" in result
        assert f"MonitorProcess(handle='{handle}')" in result

        # The report may hold no output at all: a machine slow enough to boot
        # the interpreter after the window is adopted before its first line,
        # which is what the Windows runner does (see the test below).
        before = max(_ticks(result), default=0)
        status = await _collect_until_tick_past(handle, before)

        assert "Status: running" in status
        assert _highest_tick(status) > before, "output after the timeout is lost"
    finally:
        await get_shell_background_registry().kill(handle)


@pytest.mark.asyncio
async def test_a_command_adopted_before_it_prints_is_still_collected(tmp_path):
    """The Windows runner's case: adopted while the interpreter was still starting.

    A shared runner can boot Python slower than the window, so the report holds
    no output at all — which is why the test above must not require one. The
    command is not lost: the handle is live, and what it writes afterwards still
    arrives. Giving it a quiet start makes that case happen on every machine.
    """
    result = await run_shell_command(_slow_starter_command(tmp_path), timeout=1)
    handle = _handle(result)
    try:
        assert "(moved to background after 1s)" in result
        # Nothing printed yet: the report has no tick to measure from.
        assert _ticks(result) == [], "the slow starter printed before the window"

        status = await _collect_until_tick_past(handle, 0)

        assert "Status: running" in status
        assert _highest_tick(status) > 0, "output after the timeout is lost"
    finally:
        await get_shell_background_registry().kill(handle)


@pytest.mark.asyncio
async def test_the_report_never_tells_the_model_to_run_it_again(tmp_path):
    """Re-running is what the old message asked for, and it starts the work
    over: the advice now points at the handle."""
    result = await run_shell_command(_ticker_command(tmp_path), timeout=1)
    handle = _handle(result)
    try:
        assert "background=True" not in result
        assert "Do not run the command again" in result
    finally:
        await get_shell_background_registry().kill(handle)


def _flooding_command(tmp_path, seconds: float = 30.0) -> str:
    """A script that overflows the cap, both before and after a timeout.

    The first hundred lines go out in one burst, on purpose. The test gives the
    command one second and a 400-character cap, and a loop that trickles one line
    every 20 ms from line 0 only overflows if the interpreter is warm enough to
    reach line 6 inside that second. On the shared macOS runner it is not: the
    failure showed five lines and no spill file at all, which measures interpreter
    startup on that machine rather than the adoption path. A burst makes the
    overflow happen as soon as the script runs at all, and the loop after it still
    grows the file once the command has been adopted.
    """
    script = tmp_path / "flood.py"
    script.write_text(
        "import time\n"
        "for index in range(100):\n"
        "    print('LINE', index, 'x' * 60, flush=True)\n"
        f"deadline = time.monotonic() + {seconds}\n"
        "index = 100\n"
        "while time.monotonic() < deadline:\n"
        "    print('LINE', index, 'x' * 60, flush=True)\n"
        "    index += 1\n"
        "    time.sleep(0.02)\n",
        encoding="utf-8",
    )
    return f"{_PYTHON} {shlex.quote(script.as_posix())}"


def _spill_path(text: str) -> str:
    """The overflow spill file a `Shell` report or a poll points at."""
    match = re.search(r"(\S*zrb_shell_part_\S*\.log)", text)
    assert match is not None, text
    return match.group(1)


def _highest_line(path: str) -> int:
    with open(path, "r", encoding="utf-8", errors="replace") as spilled:
        numbers = [
            int(n) for n in re.findall(r"^LINE (\d+)", spilled.read(), re.MULTILINE)
        ]
    assert numbers, "nothing of the command's output is in the file"
    return max(numbers)


@pytest.mark.asyncio
async def test_an_adopted_flood_keeps_one_complete_spill_file(tmp_path):
    """The file the report names must hold the command's whole output.

    Dumping the overflow closes the capture's spill; the next overflow then
    opens a new file holding only what was written after adoption — a path that
    claims to be the command's output while starting mid-stream.
    """
    window = await _window_outlasting_startup()
    result = await run_shell_command(
        _flooding_command(tmp_path), timeout=window, max_chars=400
    )
    handle = _handle(result)
    try:
        spill = _spill_path(result)
        before = _highest_line(spill)
        await asyncio.sleep(0.4)
        status = await get_shell_background_registry().collect(handle)

        assert "LINE 0 " in open(spill, encoding="utf-8").read()
        assert _highest_line(spill) > before, "the file stopped growing"
        assert _spill_path(status) == spill, "a second spill file claimed the output"
    finally:
        await get_shell_background_registry().kill(handle)


@pytest.mark.asyncio
async def test_a_sleep_still_dies_at_its_timeout():
    """A delay is the work: backgrounding it would let the next command run
    before the wait it was waiting for was over."""
    result = await run_shell_command("sleep 30", timeout=1)

    assert "(timed out)" in result
    assert "Handle:" not in result


@pytest.mark.asyncio
async def test_adoption_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS", 0)

    result = await run_shell_command(_ticker_command(tmp_path), timeout=1)

    assert "(timed out)" in result
    assert "Handle:" not in result


@pytest.mark.asyncio
async def test_an_adopted_process_is_stopped_at_its_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS", 1)
    result = await run_shell_command(_ticker_command(tmp_path), timeout=1)
    handle = _handle(result)

    await asyncio.sleep(2)
    status = await get_shell_background_registry().collect(handle)

    assert "killed after 1s in the background" in status
    assert "Status: exited" in status
    assert "[zrb]" in status


@pytest.mark.asyncio
async def test_the_deadline_notice_names_the_configured_cli(tmp_path, monkeypatch):
    """A white-labeled build does not tell its user that `zrb` stopped it."""
    monkeypatch.setattr(CFG, "LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS", 1)
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "acme")
    result = await run_shell_command(_ticker_command(tmp_path), timeout=1)
    handle = _handle(result)

    await asyncio.sleep(2)
    status = await get_shell_background_registry().collect(handle)

    assert "[acme] killed after 1s in the background" in status
    assert "[zrb]" not in status
