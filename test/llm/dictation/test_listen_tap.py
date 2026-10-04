"""The tap: what the microphone hands over as it captures.

The tap is filled from the audio callback, beside the backlog the reading loop
drains, and handed over by a task of its own — so it sees every block the
microphone captured, not only the ones the reader got to (ADR-0107, stage 1).
Closing it is the teardown of the microphone that stopped feeding it, which is
what the second test here is about.

The microphone is a fake `sounddevice` whose `InputStream` hands its callback to
the test, which then plays blocks into it; opening that microphone is
`test_listen_microphone.py`'s, and the backlog the reader keeps is
`test_listen.py`'s.
"""

import asyncio
import importlib
import logging
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.listen import listen

np = pytest.importorskip("numpy")


class FakeStream:
    """A `sounddevice.InputStream`: started by `_open_microphone`, closed when
    the listening stops."""

    def __init__(self):
        self.is_started = False
        self.is_closed = False

    def start(self):
        self.is_started = True

    def close(self):
        self.is_closed = True


def _fake_sounddevice(captured):
    def make_stream(**kwargs):
        captured.update(kwargs)
        return FakeStream()

    fake_sd = MagicMock()
    fake_sd.InputStream.side_effect = make_stream
    return fake_sd


def _holds_for(checks):
    """A should_record/should_listen that holds for *checks* calls."""
    remaining = [checks]

    def should_continue():
        remaining[0] -= 1
        return remaining[0] >= 0

    return should_continue


def _block(value):
    return np.full((2, 1), value, dtype=np.float32)


def _pcm(*values):
    return (np.array(values, dtype=np.float32) * 32767).astype(np.int16).tobytes()


async def _play(captured, blocks):
    await asyncio.sleep(0)  # let the coroutine open the stream
    for block in blocks:
        captured["callback"](block, len(block), None, None)


def _tap_config(max_backlog):
    """0.1 s blocks: speech starts at a loud block and ends after 2 quiet ones."""
    return DictationConfig(
        threshold=0.1,
        silence=0.2,
        min_speech=0.1,
        max_utterance=10,
        pre_roll=0,
        max_backlog=max_backlog,
    )


async def _collect_with(config, blocks, on_captured=None):
    """Feed every block before the listener reads any, as happens while the
    caller is busy transcribing."""
    captured = {}

    async def consume():
        stream = listen(
            config,
            _holds_for(len(blocks)),
            keep_partial=True,
            on_captured=on_captured,
        )
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, blocks)
        return await task


@pytest.mark.asyncio
async def test_the_capture_reaches_the_tap_even_when_the_backlog_drops_it():
    """The tap is fed as blocks are captured, not as the reader reads them.

    The reader stops while an utterance is transcribed and answered, and the
    blocks the microphone captures meanwhile pile up behind it. What the
    hand-off promises is every captured block, so a block the backlog drops must
    still reach `on_captured` (PR #561 review).
    """
    blocks = [_block(0.5)] * 3
    seen: list[bytes] = []

    async def on_captured(pcm: bytes) -> None:
        seen.append(pcm)

    # Room for one block in the backlog, so the reader keeps the last one only.
    await _collect_with(_tap_config(0.1), blocks, on_captured=on_captured)

    assert seen == [_pcm(0.5, 0.5)] * 3


@pytest.mark.asyncio
async def test_a_hand_over_that_will_not_stop_does_not_hold_the_close(
    monkeypatch, caplog
):
    """A hand-over that swallows its cancel is named and left, not waited on
    (PR #561 review).

    Closing the tap is the teardown of the microphone that stopped feeding it, so
    the hand-over is given until the deadline and no longer, and the cancel that
    follows the deadline is bounded the same way. A hand-over stuck in work that
    ignores the cancel cannot be ended from here; what it must not do is hold the
    teardown for as long as it likes.
    """
    # Reached through `importlib` rather than a dotted name: the
    # `zrb.llm.dictation` package exports a *function* called `listen`, which is
    # what a dotted name resolves to where the module of the same name lives.
    listen_module = importlib.import_module("zrb.llm.dictation.listen")
    monkeypatch.setattr(listen_module, "_TAP_CLOSE_SECONDS", 0.05)
    started = asyncio.Event()
    handing_over: list[asyncio.Task] = []

    async def stuck(pcm: bytes) -> None:
        task = asyncio.current_task()
        assert task is not None
        handing_over.append(task)
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            # Outlives the deadline below, and then fails: the exception of a task
            # nobody awaits is read off where it lands, not logged by the loop.
            await asyncio.sleep(0.2)
            raise RuntimeError("the hand-over failed on the way out") from None

    captured = {}

    async def consume():
        stream = listen(_tap_config(1.0), _holds_for(1), on_captured=stuck)
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": _fake_sounddevice(captured)}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
        caplog.at_level(logging.WARNING),
    ):
        task = asyncio.create_task(consume())
        await _play(captured, [_block(0.5)])
        await started.wait()
        await asyncio.wait_for(task, timeout=5)

    assert "The capture hand-over is still running after being cancelled" in caplog.text

    await asyncio.wait({handing_over[0]}, timeout=1)
    assert isinstance(handing_over[0].exception(), RuntimeError)
