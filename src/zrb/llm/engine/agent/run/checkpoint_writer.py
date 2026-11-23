"""Mid-turn history persistence: the coalescing writer behind `checkpoint_fn`.

`create_checkpoint_writer` is what one turn gets, and `drain_checkpoints` is what
the turn's `finally` owes it. Both live here rather than in `runner.py` so the
turn loop reads as a sequence of steps, each of which already had its own module
(`turn_cursor`, `retry_loop`, `deferred_calls`, `session_extension`,
`partial_run`, `turn_snapshot`).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from zrb.llm.engine.agent.run.typing_aliases import CheckpointFn, History


class CheckpointWriter:
    """Persist mid-turn history, newest snapshot wins.

    A checkpoint is a recovery boundary, not a journal: a snapshot a newer one
    has already replaced holds nothing a resumed process would want, and it
    costs a full serialization of the history to write, once per tool round. So
    one write runs at a time, and a boundary that arrives behind it replaces the
    snapshot waiting instead of queueing behind it: a twenty-round turn writes
    the history twice, not twenty times, and the last snapshot still goes out
    before `drain` returns.
    """

    def __init__(self, checkpoint_fn: CheckpointFn) -> None:
        self._checkpoint_fn = checkpoint_fn
        self._latest: History | None = None
        self._in_flight: asyncio.Task | None = None

    def submit(self, snapshot: History) -> None:
        """Offer *snapshot*, replacing one that is still waiting to be written."""
        self._latest = snapshot
        if self._in_flight is None:
            self._in_flight = asyncio.create_task(self._write_until_caught_up())

    async def _write_until_caught_up(self) -> None:
        while self._latest is not None:
            snapshot = self._latest
            self._latest = None
            try:
                results = await asyncio.gather(
                    self._checkpoint_fn(snapshot), return_exceptions=True
                )
            except Exception:
                # The checkpointer raised before it handed back an awaitable, or
                # handed back something that is not one. The task keeps the
                # failure for `drain` to retrieve, and the snapshot it owed
                # stays waiting unless a newer one has replaced it.
                if self._latest is None:
                    self._latest = snapshot
                raise
            for result in results:
                if isinstance(result, Exception):
                    CFG.LOGGER.warning(f"Checkpoint save failed: {result}")
        self._in_flight = None

    async def drain(self) -> None:
        """Wait for every write this writer owes, the last snapshot included.

        A write that failed before it could reach `_latest` is awaited here:
        that is where its failure is retrieved, rather than left to the event
        loop's garbage collector, and the snapshot still waiting gets the
        attempt the failed write never made.
        """
        task = self._in_flight
        if task is None:
            return
        try:
            await task
        except Exception as e:
            CFG.LOGGER.warning(f"Checkpoint save failed: {e}")
            if self._latest is not None:
                try:
                    await self._write_until_caught_up()
                except Exception as retry_error:
                    CFG.LOGGER.warning(f"Checkpoint save failed: {retry_error}")
        finally:
            self._in_flight = None


def create_checkpoint_writer(
    checkpoint_fn: CheckpointFn | None,
) -> CheckpointWriter | None:
    """One writer per turn, or none when the caller asked for no checkpoints."""
    if checkpoint_fn is None:
        return None
    return CheckpointWriter(checkpoint_fn)


async def drain_checkpoints(writer: CheckpointWriter | None) -> None:
    """Wait for this turn's writes, so none lands after the end-of-turn save."""
    if writer is None:
        return
    await writer.drain()
