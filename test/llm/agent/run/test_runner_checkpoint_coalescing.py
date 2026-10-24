"""A checkpoint write is replaceable work: newest snapshot wins, one at a time.

The runner used to spawn one write per tool round and gather them all when the
turn ended — 19 ms and 4.3 MB of serialization each on a 406-message history,
twenty of them for a twenty-round turn, every one writing a history that the
next one immediately superseded. What a resumed process wants is the most recent
complete history, so an older snapshot that a newer one has replaced can be
dropped as long as the last one is always written.
"""

import asyncio
import logging

import pytest

from zrb.llm.agent.run.runner import _CheckpointWriter


async def _until(condition, attempts: int = 200) -> None:
    """Let the event loop run until *condition* holds, without a sleep."""
    for _ in range(attempts):
        if condition():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition never became true")


@pytest.mark.asyncio
async def test_a_busy_writer_keeps_only_the_newest_snapshot():
    """Five boundaries behind one slow write: the first and the last, not five.

    The three in between describe histories the fifth already contains.
    """
    release = asyncio.Event()
    written: list[list] = []

    async def slow_write(snapshot):
        written.append(snapshot)
        await release.wait()

    writer = _CheckpointWriter(slow_write)
    writer.submit(["a"])
    await _until(lambda: written == [["a"]])
    for name in ("b", "c", "d"):
        writer.submit([name])

    release.set()
    await writer.drain()

    assert written == [["a"], ["d"]]


@pytest.mark.asyncio
async def test_a_writer_that_keeps_up_writes_every_snapshot():
    """Coalescing must not become lossiness: with time to write, nothing drops."""
    written: list[list] = []

    async def write(snapshot):
        written.append(snapshot)

    writer = _CheckpointWriter(write)
    for name in ("a", "b", "c"):
        writer.submit([name])
        await _until(lambda: written[-1:] == [[name]])

    await writer.drain()

    assert written == [["a"], ["b"], ["c"]]


@pytest.mark.asyncio
async def test_drain_waits_for_the_write_it_owes():
    """The turn's own end-of-turn save must not race a lagging checkpoint."""
    release = asyncio.Event()
    written: list[list] = []

    async def slow_write(snapshot):
        await release.wait()
        written.append(snapshot)

    writer = _CheckpointWriter(slow_write)
    writer.submit(["last"])
    draining = asyncio.create_task(writer.drain())
    await asyncio.sleep(0)

    assert written == []
    assert not draining.done()

    release.set()
    await draining

    assert written == [["last"]]


@pytest.mark.asyncio
async def test_a_failed_write_is_reported_and_does_not_stop_the_next(caplog):
    """A checkpoint that cannot be written is a warning, not the end of the run."""
    written: list[list] = []

    async def write(snapshot):
        if snapshot == ["bad"]:
            raise RuntimeError("disk full")
        written.append(snapshot)

    writer = _CheckpointWriter(write)
    with caplog.at_level(logging.WARNING):
        writer.submit(["bad"])
        await _until(lambda: "disk full" in caplog.text)
        writer.submit(["good"])
        await writer.drain()

    assert written == [["good"]]
    assert "Checkpoint save failed: disk full" in caplog.text


@pytest.mark.asyncio
async def test_a_snapshot_submitted_after_the_writer_went_idle_is_still_written():
    """The idle gap is the easy place to lose a snapshot: the task exited
    between the loop's last check and the next submit."""
    written: list[list] = []

    async def write(snapshot):
        written.append(snapshot)

    writer = _CheckpointWriter(write)
    writer.submit(["a"])
    await _until(lambda: written == [["a"]])
    await asyncio.sleep(0)  # the in-flight task finishes and clears itself
    writer.submit(["b"])
    await writer.drain()

    assert written == [["a"], ["b"]]
