"""An utterance's transcription stream is closed whenever it is abandoned
instead of finished (`AnyTranscriptionStream`'s contract)."""

import asyncio
import contextlib

import pytest

from zrb.llm.dictation import (
    AnyDictationBackend,
    AnyTranscriptionStream,
    DictationConfig,
)
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import Utterance


class FakeBackend(AnyDictationBackend):
    async def transcribe(self, audio: bytes) -> str:
        return audio.decode()


class FakeStream(AnyTranscriptionStream):
    def __init__(self, finish=None, fail_close=False):
        self._finish = finish
        self.fail_close = fail_close
        self.closed = 0
        self.started = asyncio.Event()

    async def feed(self, audio):
        pass

    @property
    def partial(self):
        return ""

    async def finish(self):
        self.started.set()
        if self._finish is None:
            await asyncio.Event().wait()  # never finishes on its own
        return await self._finish()

    async def close(self):
        self.closed += 1
        if self.fail_close:
            raise OSError("socket already gone")


def _session(monkeypatch, stream):
    async def listen(config, should_listen, **kwargs):
        yield Utterance(b"audio", 0, 1, False, stream)
        await asyncio.Event().wait()

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))
    config = DictationConfig(
        backend=FakeBackend(), mode="hands_free", hands_free_commands=["/handsfree"]
    )
    return DictationSession(config.resolve())


async def _start(session):
    stream = session.listen_hands_free()
    task = asyncio.ensure_future(anext(stream))
    return stream, task


async def _stop(stream, task):
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
        await task
    await stream.aclose()


@pytest.mark.asyncio
async def test_switching_hands_free_off_mid_finish_closes_the_stream(monkeypatch):
    fake = FakeStream()
    session = _session(monkeypatch, fake)
    stream, task = await _start(session)
    await asyncio.wait_for(fake.started.wait(), 1)

    [command] = [c for c in session.create_commands() if c.command == "/handsfree"]
    command.handle({}, None)  # switch off
    await asyncio.sleep(0.05)

    assert fake.closed == 1
    await _stop(stream, task)


@pytest.mark.asyncio
async def test_a_failing_finish_closes_the_stream(monkeypatch):
    async def fail():
        raise RuntimeError("decoder crashed")

    fake = FakeStream(finish=fail)
    session = _session(monkeypatch, fake)
    stream, task = await _start(session)
    await asyncio.sleep(0.05)

    assert fake.closed == 1
    await _stop(stream, task)


@pytest.mark.asyncio
async def test_cancelling_the_listener_mid_finish_closes_the_stream(monkeypatch):
    fake = FakeStream()
    session = _session(monkeypatch, fake)
    stream, task = await _start(session)
    await asyncio.wait_for(fake.started.wait(), 1)

    await _stop(stream, task)

    assert fake.closed == 1


@pytest.mark.asyncio
async def test_a_stream_that_fails_to_close_is_logged_not_raised(monkeypatch, caplog):
    async def fail():
        raise RuntimeError("decoder crashed")

    fake = FakeStream(finish=fail, fail_close=True)
    session = _session(monkeypatch, fake)
    stream, task = await _start(session)
    await asyncio.sleep(0.05)

    assert "socket already gone" in caplog.text
    await _stop(stream, task)


@pytest.mark.asyncio
async def test_a_finished_stream_is_not_closed_again(monkeypatch):
    async def done():
        return "hello"

    fake = FakeStream(finish=done)
    session = _session(monkeypatch, fake)
    stream = session.listen_hands_free()

    reply = await anext(stream)
    await stream.aclose()

    assert reply.text == "hello"
    assert fake.closed == 0
