"""A command that outruns its timeout keeps running, under a handle.

The timeout used to kill the process, so everything it had already done was
lost and the model was told to run it again — a second copy of the work. It is
now moved to the background instead, and these tests hold that shape.
"""

import asyncio
import re
import shlex
import sys
from pathlib import Path

import pytest

from zrb.config.config import CFG
from zrb.llm.tool.shell import run_shell_command
from zrb.llm.tool.shell_background import get_shell_background_registry

_PYTHON = shlex.quote(Path(sys.executable).as_posix())


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


def _highest_tick(text: str) -> int:
    ticks = [int(index) for index in re.findall(r"TICK (\d+)", text)]
    assert ticks, text
    return max(ticks)


@pytest.mark.asyncio
async def test_a_timed_out_command_keeps_running_under_a_handle(tmp_path):
    result = await run_shell_command(_ticker_command(tmp_path), timeout=1)
    handle = _handle(result)
    try:
        assert "(moved to background after 1s)" in result
        assert "NOT killed" in result
        assert f"MonitorProcess(handle='{handle}')" in result

        before = _highest_tick(result)
        await asyncio.sleep(0.5)
        status = await get_shell_background_registry().collect(handle)

        assert "Status: running" in status
        assert _highest_tick(status) > before, "output after the timeout is lost"
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
        numbers = [int(n) for n in re.findall(r"^LINE (\d+)", spilled.read(), re.MULTILINE)]
    assert numbers, "nothing of the command's output is in the file"
    return max(numbers)


@pytest.mark.asyncio
async def test_an_adopted_flood_keeps_one_complete_spill_file(tmp_path):
    """The file the report names must hold the command's whole output.

    Dumping the overflow closes the capture's spill; the next overflow then
    opens a new file holding only what was written after adoption — a path that
    claims to be the command's output while starting mid-stream.
    """
    result = await run_shell_command(
        _flooding_command(tmp_path), timeout=1, max_chars=400
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
