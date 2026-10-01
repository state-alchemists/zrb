"""`listen` feeding each utterance to a transcription stream while it is
spoken, and ending it early once it sounds finished."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.dictation import AnyTranscriptionStream
from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.listen import listen

np = pytest.importorskip("numpy")


class FakeStream:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class RecordingStream(AnyTranscriptionStream):
    def __init__(self, words):
        self.words = list(words)
        self.fed: list[bytes] = []
        self.closed = False
        self._heard = ""

    async def feed(self, audio):
        self.fed.append(audio)
        if self.words:
            self._heard = " ".join(filter(None, [self._heard, self.words.pop(0)]))

    @property
    def partial(self):
        return self._heard

    async def finish(self):
        return self._heard

    async def close(self):
        self.closed = True


def _block(value):
    return np.full((2, 1), value, dtype=np.float32)


def _config(**fields):
    base = dict(
        threshold=0.1,
        silence=0.5,
        min_silence=0.2,
        min_speech=0.1,
        max_utterance=10,
        pre_roll=0,
        echo_cooldown=0,
    )
    return DictationConfig(**{**base, **fields}).resolve()


async def _collect(blocks, streams, config=None, partials=None):
    captured = {}
    made = list(streams)

    async def create_stream():
        return made.pop(0) if made else None

    def make_input_stream(**kwargs):
        captured.update(kwargs)
        return FakeStream()

    fake_sd = MagicMock()
    fake_sd.InputStream.side_effect = make_input_stream
    remaining = [len(blocks)]

    def should_listen():
        remaining[0] -= 1
        return remaining[0] >= 0

    async def consume():
        stream = listen(
            config or _config(),
            should_listen,
            create_stream=create_stream,
            on_partial=None if partials is None else partials.append,
        )
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": fake_sd}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
    ):
        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        for block in blocks:
            captured["callback"](block, len(block), None, None)
        return await task


@pytest.mark.asyncio
async def test_an_utterance_is_fed_to_its_stream_as_it_is_spoken():
    stream = RecordingStream(["run", "the", "tests"])
    partials = []
    blocks = [_block(0.5)] * 3 + [_block(0.0)] * 5

    [utterance] = await _collect(blocks, [stream], partials=partials)

    assert utterance.stream is stream
    assert b"".join(stream.fed) == utterance.audio
    assert partials[:3] == ["run", "run the", "run the tests"]


@pytest.mark.asyncio
async def test_an_utterance_that_sounds_finished_ends_after_min_silence():
    blocks = [_block(0.5)] * 2 + [_block(0.0)] * 2
    [utterance] = await _collect(blocks, [RecordingStream(["open", "it"])])
    assert utterance.stream.partial == "open it"


@pytest.mark.asyncio
async def test_an_utterance_trailing_off_waits_for_the_full_silence():
    blocks = [_block(0.5)] * 2 + [_block(0.0)] * 2
    assert await _collect(blocks, [RecordingStream(["open", "the"])]) == []

    blocks = [_block(0.5)] * 2 + [_block(0.0)] * 5
    [utterance] = await _collect(blocks, [RecordingStream(["open", "the"])])
    assert utterance.stream.partial == "open the"


@pytest.mark.asyncio
async def test_a_cough_abandons_its_stream():
    stream = RecordingStream(["uh"])
    config = _config(min_speech=0.3)
    blocks = [_block(0.5)] + [_block(0.0)] * 6

    assert await _collect(blocks, [stream], config=config) == []
    assert stream.closed


@pytest.mark.asyncio
async def test_a_batch_backend_is_asked_for_a_stream_only_once():
    asked = []

    async def create_stream():
        asked.append(True)
        return None

    captured = {}
    fake_sd = MagicMock()
    fake_sd.InputStream.side_effect = lambda **kw: captured.update(kw) or FakeStream()
    blocks = [_block(0.5)] * 3 + [_block(0.0)] * 6
    remaining = [len(blocks)]

    def should_listen():
        remaining[0] -= 1
        return remaining[0] >= 0

    async def consume():
        stream = listen(_config(), should_listen, create_stream=create_stream)
        return [u async for u in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": fake_sd}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
    ):
        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        for block in blocks:
            captured["callback"](block, len(block), None, None)
        [utterance] = await task

    assert asked == [True]
    assert utterance.stream is None
