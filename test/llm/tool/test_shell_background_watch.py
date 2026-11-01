"""A background process records its watch, and the live context shows it once.

The registry is what starts and ends the work; the ledger is what survives it.
These tests hold the join between them, and the one line the next turn gets.
"""

import asyncio
import os

import pytest

from zrb.config.config import CFG
from zrb.llm.prompt import live_context
from zrb.llm.tool.shell_background import (
    _release_process,
    get_shell_background_registry,
)
from zrb.llm.watch import WatchLedger, reset_watch_ledgers


@pytest.fixture
def watch_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_WATCH_DIR", str(tmp_path))
    reset_watch_ledgers()
    yield tmp_path
    reset_watch_ledgers()


@pytest.mark.asyncio
async def test_a_background_process_is_recorded_and_closed(watch_dir):
    """Starting and ending are both in the ledger, without anyone polling."""
    registry = get_shell_background_registry()

    handle = await registry.start("exit 3", "", "Failing on purpose")
    await registry.collect(handle, wait=10)

    ledger = WatchLedger(str(watch_dir), "_")
    (record,) = ledger.records()
    assert record.id == handle
    assert record.what == "Failing on purpose"
    assert record.state == "finished"
    assert record.exit_code == 3


@pytest.mark.asyncio
async def test_a_killed_process_is_not_recorded_as_finished(watch_dir):
    """A kill is an ending, and it must not read as a success."""
    registry = get_shell_background_registry()

    handle = await registry.start("sleep 30", "", "Sleeping until killed")
    await registry.kill(handle)

    (record,) = WatchLedger(str(watch_dir), "_").records()
    assert record.state == "killed"


@pytest.mark.asyncio
async def test_the_watch_is_on_disk_before_the_process_exists(watch_dir, monkeypatch):
    """A crash between the spawn and the record would lose the work entirely."""
    import asyncio

    seen: dict[str, list[str]] = {}
    spawn = asyncio.create_subprocess_exec

    async def spy(*args, **kwargs):
        seen["rows"] = [
            record.id for record in WatchLedger(str(watch_dir), "_").records()
        ]
        return await spawn(*args, **kwargs)

    monkeypatch.setattr("asyncio.create_subprocess_exec", spy)
    registry = get_shell_background_registry()

    handle = await registry.start("exit 0", "", "Recorded before it ran")
    await registry.collect(handle, wait=10)

    assert seen["rows"] == [handle]


@pytest.mark.asyncio
async def test_a_command_that_never_started_says_so(watch_dir, monkeypatch):
    """A failed spawn is not "outcome unknown": nothing ran."""

    async def refuse(*args, **kwargs):
        raise OSError("no such shell")

    monkeypatch.setattr("asyncio.create_subprocess_exec", refuse)
    registry = get_shell_background_registry()

    with pytest.raises(OSError):
        await registry.start("exit 0", "", "Never ran")

    (record,) = WatchLedger(str(watch_dir), "_").records()
    assert record.state == "failed"


@pytest.mark.asyncio
async def test_a_shutdown_kill_closes_the_watch(watch_dir):
    """`atexit` has no event loop left, so the row must be closed by hand."""
    registry = get_shell_background_registry()

    handle = await registry.start("sleep 30", "", "Killed at shutdown")
    bp = registry._procs[handle]
    registry.force_kill_all()
    # The atexit path never looks back; the test must, or the dead process's
    # transport is collected unclosed inside whichever test runs next.
    await bp.process.wait()
    _release_process(bp)

    (record,) = WatchLedger(str(watch_dir), "_").records()
    assert record.id == handle
    assert record.state == "killed"


@pytest.mark.asyncio
async def test_a_shutdown_does_not_relabel_a_finished_process(watch_dir):
    """An exit that already happened must not be recorded as a kill."""
    registry = get_shell_background_registry()
    handle = await registry.start("exit 0", "", "Finished before shutdown")
    await registry.collect(handle, wait=10)

    registry.force_kill_all()

    (record,) = WatchLedger(str(watch_dir), "_").records()
    assert record.state == "finished"
    assert record.exit_code == 0


@pytest.mark.asyncio
async def test_a_ledger_that_cannot_record_the_ending_still_leaves_one(
    watch_dir, monkeypatch
):
    """The command wrote its own exit code, so a lost ending row is not lost."""

    def refuse(self, *args, **kwargs):
        raise OSError("the ledger went away")

    monkeypatch.setattr(WatchLedger, "end", refuse)
    registry = get_shell_background_registry()

    handle = await registry.start("exit 5", "", "Bookkeeping failed at the end")
    await registry.collect(handle, wait=10)
    for _ in range(100):
        if os.path.exists(WatchLedger(str(watch_dir), "_").exit_file_for(handle)):
            break
        await asyncio.sleep(0.05)

    (record,) = WatchLedger(str(watch_dir), "_").records()
    assert record.state == "finished"
    assert record.exit_code == 5


@pytest.mark.asyncio
async def test_a_spilled_output_leaves_a_pointer_in_the_watch(watch_dir, monkeypatch):
    """The retained tail dies with the process; a spill file does not."""
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 16)
    registry = get_shell_background_registry()

    handle = await registry.start(
        'python -c "print(chr(120) * 400)"', "", "More output than the capture keeps"
    )
    await registry.collect(handle, wait=20)

    (record,) = WatchLedger(str(watch_dir), "_").records()
    assert record.outcome, "a truncated stream has somewhere to point"
    assert os.path.exists(record.outcome)
    (line,) = WatchLedger(str(watch_dir), "_").render_lines()
    assert record.outcome in line


def test_the_live_context_names_an_outcome_the_registry_has_dropped(
    watch_dir, monkeypatch
):
    """The whole point: the result is still there after the handle is gone."""
    ledger = WatchLedger(str(watch_dir), "_")
    ledger.open("gone-handle", kind="process", what="Checking the pipeline")
    ledger.end("gone-handle", 0)
    monkeypatch.setattr("zrb.llm.watch.get_watch_ledger", lambda session=None: ledger)

    lines = live_context.watch_lines()

    assert any("gone-handle" in line and "exit 0" in line for line in lines)
    assert live_context.watch_lines() == []


def test_a_live_handle_is_left_to_the_registry_section(watch_dir, monkeypatch):
    """Two sections must not say the same thing twice."""
    ledger = WatchLedger(str(watch_dir), "_")
    ledger.open("still-listed", kind="process", what="Still running")
    monkeypatch.setattr("zrb.llm.watch.get_watch_ledger", lambda session=None: ledger)

    assert live_context.watch_lines() == []


def test_an_unwritable_ledger_costs_a_section_not_the_turn(watch_dir, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_WATCH_DIR", "/proc/definitely-not-writable")

    assert live_context.watch_lines() == []


@pytest.mark.asyncio
async def test_the_watch_waits_for_the_output_before_recording_its_pointer(
    watch_dir, monkeypatch
):
    """An exit heard before the last output must not close the watch pointer-less."""
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 50)
    registry = get_shell_background_registry()
    real_read_pipe = type(registry)._read_pipe

    async def slow_read_pipe(self, handle, stream, name):
        # The exit is heard long before the output is read.
        await asyncio.sleep(0.4)
        await real_read_pipe(self, handle, stream, name)

    monkeypatch.setattr(type(registry), "_read_pipe", slow_read_pipe)

    handle = await registry.start(
        "python3 -c \"print('x' * 400)\"", "", "Printing a lot"
    )
    await registry.collect(handle, wait=10)
    for _ in range(100):
        records = WatchLedger(str(watch_dir), "_").records()
        if records and records[0].state != "running":
            break
        await asyncio.sleep(0.05)

    (record,) = WatchLedger(str(watch_dir), "_").records()
    assert record.state == "finished"
    assert record.outcome.endswith(".log")


@pytest.mark.asyncio
async def test_killing_a_process_that_already_exited_leaves_it_finished(watch_dir):
    """A kill asked for after a natural exit must not rewrite that exit."""
    registry = get_shell_background_registry()

    handle = await registry.start("exit 0", "", "Done before the kill")
    for _ in range(100):
        records = WatchLedger(str(watch_dir), "_").records()
        if records and records[0].state != "running":
            break
        await asyncio.sleep(0.05)
    await registry.kill(handle)

    (record,) = WatchLedger(str(watch_dir), "_").records()
    assert record.state == "finished"
    assert record.exit_code == 0


@pytest.mark.asyncio
async def test_the_spill_pointer_is_flushed_before_it_is_handed_out(
    watch_dir, monkeypatch
):
    """The next turn reads the file the watch names; its tail must be on disk."""
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 50)
    registry = get_shell_background_registry()

    handle = await registry.start("python3 -c \"print('x' * 400)\"", "", "Spilling")
    # Wait until the exit has been heard and drained: the command's own exit file
    # settles the state sooner than the ending row that carries the pointer.
    await registry.collect(handle, wait=10)

    (record,) = WatchLedger(str(watch_dir), "_").records()
    assert record.outcome
    with open(record.outcome, encoding="utf-8") as stream:
        assert stream.read().count("x") == 400
