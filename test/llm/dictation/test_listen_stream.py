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
    """A `sounddevice.InputStream`: started by `_open_microphone`, closed when
    the listening stops."""

    def __init__(self):
        self.is_started = False
        self.is_closed = False

    def start(self):
        self.is_started = True

    def close(self):
        self.is_closed = True


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
    )
    return DictationConfig(**{**base, **fields}).resolve()


async def _collect(
    blocks, streams, config=None, partials=None, over_speech=None, speaking=False
):
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
            on_partial_over_zrb=None if over_speech is None else over_speech.append,
        )
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": fake_sd}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=speaking),
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
async def test_live_partial_reports_speech_over_zrb_before_barge_in_minimum():
    over_speech = []
    blocks = [_block(0.5)] * 2 + [_block(0.0)] * 5

    await _collect(
        blocks,
        [RecordingStream(["stop", "stop"])],
        config=_config(barge_in_enabled=True, barge_in_min_speech=1.0),
        over_speech=over_speech,
        speaking=True,
    )

    assert over_speech[:2] == [True, True]


@pytest.mark.asyncio
async def test_an_utterance_ends_after_min_silence_once_it_has_words():
    blocks = [_block(0.5)] * 2 + [_block(0.0)] * 2
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


class FailingStream(RecordingStream):
    async def feed(self, audio):
        raise RuntimeError("connection reset")


@pytest.mark.asyncio
async def test_a_failing_stream_falls_back_to_transcribing_the_whole_utterance():
    """A stream error must not end hands-free: the utterance is still
    handed over, without a stream, and later ones stop asking for one."""
    failing = FailingStream([])
    spare = RecordingStream(["unused"])
    blocks = ([_block(0.5)] * 3 + [_block(0.0)] * 5) * 2

    first, second = await _collect(blocks, [failing, spare])

    assert failing.closed is True
    assert first.stream is None and second.stream is None
    assert first.audio and second.audio
    assert spare.fed == []


@pytest.mark.asyncio
async def test_a_stream_that_cannot_be_created_falls_back_too():
    captured = {}

    async def create_stream():
        raise RuntimeError("no model")

    def make_input_stream(**kwargs):
        captured.update(kwargs)
        return FakeStream()

    fake_sd = MagicMock()
    fake_sd.InputStream.side_effect = make_input_stream
    blocks = [_block(0.5)] * 3 + [_block(0.0)] * 5
    remaining = [len(blocks)]

    def should_listen():
        remaining[0] -= 1
        return remaining[0] >= 0

    async def consume():
        stream = listen(_config(), should_listen, create_stream=create_stream)
        return [utterance async for utterance in stream]

    with (
        patch.dict("sys.modules", {"sounddevice": fake_sd}),
        patch("zrb.llm.dictation.listen.is_speaking", return_value=False),
    ):
        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        for block in blocks:
            captured["callback"](block, len(block), None, None)
        [utterance] = await task

    assert utterance.stream is None
    assert utterance.audio
