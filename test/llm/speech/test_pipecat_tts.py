"""Slice 3 of the Pipecat migration: a sentence, said by a service, played by zrb.

No model is installed here and none is needed. What is under test is the pipeline
zrb drives: that a sentence reaches the service and its audio comes back whole,
that the rate it comes back at is the service's own, that one sentence is said at
a time, and that a sentence nobody will hear is dropped on both sides. A
`TTSService` that answers without a model stands in for Kokoro, Piper and Pocket
TTS, which are all driven the same way — the service is Pipecat's, and so is the
shape under test.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable

import pytest

pytest.importorskip("pipecat", reason="pipecat ships with the `voice` extra")

from pipecat.frames.frames import (  # noqa: E402
    Frame,
    InterruptionFrame,
    TTSAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection  # noqa: E402
from pipecat.services.settings import TTSSettings  # noqa: E402
from pipecat.services.tts_service import TTSService  # noqa: E402

from zrb.config.config import CFG  # noqa: E402
from zrb.llm.speech import pipecat_tts  # noqa: E402
from zrb.llm.speech.pipecat_tts import TTSPipeline  # noqa: E402

#: A rate none of the fixtures of this file use elsewhere, so a chunk read at
#: zrb's default would be audible as the mistake it is.
RATE = 24000

#: 800 samples of 16-bit PCM: one chunk of speech, as a service makes it.
CHUNK = b"\x11\x22" * 400

SENTENCE = "the tests are green"


class FakeSpeechService(TTSService):
    """A service that says what it is given, the way the local ones do.

    `push_start_frame` and `push_stop_frames` are what Kokoro, Piper and Pocket
    TTS ask Pipecat for: a speak frame is answered with a started frame, its
    audio, and a stopped frame. A fake without them would be testing a pipeline
    zrb never builds, and a sentence would have no end at all.
    """

    def __init__(self, chunks: int = 1, delay: float = 0.0) -> None:
        # Every settings field named, because pipecat logs an error for a field a
        # service left uninitialized.
        super().__init__(
            sample_rate=RATE,
            push_start_frame=True,
            push_stop_frames=True,
            settings=TTSSettings(model=None, voice=None, language=None),
        )
        self.said: list[str] = []
        self.chunks = chunks
        self.delay = delay
        self.interruptions = 0

    async def run_tts(self, text: str, context_id: str):
        self.said.append(text)
        interruptions = self.interruptions
        for _ in range(self.chunks):
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.interruptions != interruptions:
                # Interrupted: the sentence stops being said where it stands, and
                # the sentence after it is a new one.
                return
            yield TTSAudioRawFrame(
                audio=CHUNK, sample_rate=RATE, num_channels=1, context_id=context_id
            )

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, InterruptionFrame):
            self.interruptions += 1
        await super().process_frame(frame, direction)


class RaisingSpeechService(FakeSpeechService):
    """A service whose synthesis fails, as a real model can."""

    async def run_tts(self, text: str, context_id: str):
        self.said.append(text)
        if text:
            # `if`, not a bare raise: the yield below is what makes this an async
            # generator, and code after a `raise` cannot be reached to say so.
            raise RuntimeError("the model is unhappy")
        yield TTSAudioRawFrame(
            audio=CHUNK, sample_rate=RATE, num_channels=1, context_id=context_id
        )


class TaggedSpeechService(FakeSpeechService):
    """A service whose audio says which text it was made for.

    `FakeSpeechService`'s shape, with the one difference these tests need: the
    chunk can be traced back to the sentence it was made for, so audio left over
    from one sentence cannot pass for the next one's.
    """

    async def run_tts(self, text: str, context_id: str):
        self.said.append(text)
        interruptions = self.interruptions
        for _ in range(self.chunks):
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.interruptions != interruptions:
                return
            yield TTSAudioRawFrame(
                audio=text.encode(),
                sample_rate=RATE,
                num_channels=1,
                context_id=context_id,
            )


def _tts_threads() -> list[threading.Thread]:
    """The pipeline threads of this process, by the name they are given."""
    prefix = f"{CFG.ROOT_GROUP_NAME}-speech-tts"
    return [thread for thread in threading.enumerate() if thread.name == prefix]


def _wait_until(predicate: "Callable[[], bool]", timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_a_sentence_reaches_the_service_and_its_audio_comes_back():
    """The sentence zrb hands over is what is said, and what comes back is played.

    The rate is the one the service rendered at, not one zrb assumed: a local
    voice may render at 22050 or 24000, and playing either at 16000 is a sentence
    the user hears as a slur.
    """
    service = FakeSpeechService()
    pipeline = TTSPipeline.start(service)
    try:
        audio = pipeline.speak(SENTENCE, timeout=5)
        chunks = list(audio.chunks)
        sample_rate = audio.sample_rate
    finally:
        pipeline.close()

    assert service.said == [SENTENCE]
    assert chunks == [CHUNK]
    assert sample_rate == RATE


def test_the_pipeline_says_one_sentence_after_another():
    """The pipeline outlives the sentence, so a model is loaded once.

    Kokoro, Piper and Pocket TTS all load their model inside the service's
    constructor, which is the cost this pipeline is long-lived to avoid paying per
    sentence; that the second sentence is said at all is what shows the first one
    did not leave the recorder waiting for its own end.
    """
    service = FakeSpeechService()
    pipeline = TTSPipeline.start(service)
    try:
        first = list(pipeline.speak(SENTENCE, timeout=5).chunks)
        second = list(pipeline.speak(SENTENCE, timeout=5).chunks)
    finally:
        pipeline.close()

    assert first == [CHUNK]
    assert second == [CHUNK]
    assert service.said == [SENTENCE, SENTENCE]


def test_a_sentence_is_said_one_at_a_time():
    """A second sentence waits for the first: one service is one voice.

    Two sentences in flight would put two streams of audio in one queue, and a
    sentence cannot be dropped or held on its own once they are mixed. Playback is
    untouched by the wait: it is the speaker's other thread that is held up, while
    the sentence being heard goes on being heard.
    """
    service = FakeSpeechService()
    pipeline = TTSPipeline.start(service)
    try:
        first = pipeline.speak(SENTENCE, timeout=5)
        said_second: list[list[bytes]] = []
        is_said = threading.Event()

        def say_second() -> None:
            audio = pipeline.speak(SENTENCE, timeout=5)
            said_second.append(list(audio.chunks))
            is_said.set()

        threading.Thread(target=say_second, daemon=True).start()
        assert not is_said.wait(
            0.3
        ), "the second sentence started before the first ended"
        # Reading the first sentence to its end is what frees the second.
        assert list(first.chunks) == [CHUNK]
        assert is_said.wait(5)
    finally:
        pipeline.close()

    assert said_second == [[CHUNK]]


def test_dropping_a_sentence_ends_the_read_at_once_and_the_synthesis_with_it():
    """A sentence the user talked over is dropped, not played out.

    `SpeechAudio.close` is what playback calls when it is stopped, and it has to
    end the read there and then: a reader that drained the rest of the sentence
    first would play the audio the user just interrupted. The service is told too,
    so a sentence nobody will hear is not synthesized to its end — and the sentence
    after it is not the one that interruption lands on.
    """
    service = FakeSpeechService(chunks=5, delay=0.2)
    pipeline = TTSPipeline.start(service)
    try:
        audio = pipeline.speak(SENTENCE, timeout=5)
        read = iter(audio.chunks)
        assert next(read) == CHUNK

        dropped_at = time.monotonic()
        audio.close()
        with pytest.raises(StopIteration):
            next(read)
        assert time.monotonic() - dropped_at < 1.0

        assert _wait_until(lambda: service.interruptions == 1)
        after = list(pipeline.speak(SENTENCE, timeout=5).chunks)
    finally:
        pipeline.close()

    assert after == [CHUNK] * 5


def test_a_service_that_refuses_the_interruption_does_not_hold_the_next_sentence(
    monkeypatch,
):
    """A failure telling the service to stop does not take the next sentence with it.

    A sentence holds the lock from the moment it is asked for until its audio is
    read or dropped, which is what makes one service one voice at a time. `_drop`
    gave that lock back after the interruption, so a failure outside the two types
    its handler names escaped with the lock still held — and every later `speak`
    waited for a sentence that had already been dropped, leaving the pipeline
    unusable for the rest of the session. The interruption only says the audio
    nobody will hear can stop being made; the drop happens either way.
    """
    service = FakeSpeechService()
    pipeline = TTSPipeline.start(service)

    def refused(loop, coroutine, timeout=None):
        coroutine.close()  # never run: the interruption never reached the service
        raise ValueError("the service refused the interruption")

    try:
        audio = pipeline.speak(SENTENCE, timeout=5)
        assert next(iter(audio.chunks)) == CHUNK  # read, but not to its end

        # The interruption is made to fail with a type the drop does not name, and
        # the pipeline gets its own call back as soon as it has: the audio is dropped
        # either way, so the sentence after it is what says whether the lock came
        # back with the drop.
        with monkeypatch.context() as failing:
            failing.setattr(pipecat_tts, "_call", refused)
            try:
                audio.close()
            except ValueError:
                # Reported to whoever dropped the audio, which logs it and goes on.
                pass

        said: "list[list[bytes]]" = []
        is_said = threading.Event()

        def say_next() -> None:
            said.append(list(pipeline.speak(SENTENCE, timeout=5).chunks))
            is_said.set()

        threading.Thread(target=say_next, daemon=True).start()
        assert is_said.wait(
            5
        ), "the sentence after a failed interruption never started"
    finally:
        pipeline.close()

    assert said == [[CHUNK]]
    assert service.said == [SENTENCE, SENTENCE]


def test_a_service_that_cannot_say_the_sentence_is_reported_before_it_is_played():
    """A failure is raised where the sentence is prepared, not where it is heard.

    This is the difference between a session that says the sentence through the
    local voice instead and one that plays half a sentence and goes quiet.
    """
    service = RaisingSpeechService()
    pipeline = TTSPipeline.start(service)
    try:
        with pytest.raises(RuntimeError):
            pipeline.speak(SENTENCE, timeout=5)
    finally:
        pipeline.close()

    assert service.said == [SENTENCE]


def test_a_sentence_that_never_arrives_tells_the_service_to_stop():
    """A sentence that timed out is dropped, not merely let go of.

    The service may still be making it: giving up the claim alone leaves it
    synthesizing audio nobody will hear, and leaves the sink about to hand
    whatever comes out to whichever sentence replaces this one.
    """
    service = FakeSpeechService(chunks=1, delay=0.5)
    pipeline = TTSPipeline.start(service)
    try:
        with pytest.raises(RuntimeError, match="said nothing"):
            pipeline.speak(SENTENCE, timeout=0.05)
        assert _wait_until(lambda: service.interruptions == 1)
    finally:
        pipeline.close()


def test_audio_from_a_sentence_that_timed_out_is_not_played_as_the_next_one():
    """What one sentence never delivered is not heard as the sentence after it.

    A first chunk that does not arrive in time leaves the service still making
    that sentence, and the sentence after it takes over the sink that the audio
    would be written to — so the previous text is played under this one's turn.
    The words are the test: a chunk carrying the earlier text failing to arrive
    as the later sentence's own is the difference the interrupt makes.
    """
    service = TaggedSpeechService(chunks=2, delay=0.5)
    pipeline = TTSPipeline.start(service)
    try:
        with pytest.raises(RuntimeError, match="said nothing"):
            pipeline.speak("first", timeout=0.05)
        second = pipeline.speak("second", timeout=5)
        first_chunk = next(iter(second.chunks))
        second.close()
    finally:
        pipeline.close()

    assert first_chunk == b"second"
    assert service.said == ["first", "second"]


def test_a_pipeline_that_has_been_closed_fails_the_next_sentence_at_once():
    """A closed pipeline is not waited on for a sentence it cannot say."""
    pipeline = TTSPipeline.start(FakeSpeechService())
    pipeline.close()

    with pytest.raises(RuntimeError, match="closed"):
        pipeline.speak(SENTENCE, timeout=5)


def test_closing_a_pipeline_leaves_no_thread_running():
    """The pipeline's loop thread ends with it, and closing twice is safe.

    A session closes its voice while the chat goes on, so a thread left running is
    a thread nothing will ever collect — and a thread that outlives the interpreter
    is worse than that.
    """
    assert _tts_threads() == []
    pipeline = TTSPipeline.start(FakeSpeechService())
    list(pipeline.speak(SENTENCE, timeout=5).chunks)
    pipeline.close()
    pipeline.close()

    assert _tts_threads() == []


def test_closing_a_pipeline_cancels_what_is_still_running_on_its_loop():
    class LingeringSpeechService(FakeSpeechService):
        lingering: "asyncio.Task[None] | None" = None

        async def run_tts(self, text: str, context_id: str):
            LingeringSpeechService.lingering = asyncio.create_task(asyncio.sleep(600))
            async for frame in super().run_tts(text, context_id):
                yield frame

    pipeline = TTSPipeline.start(LingeringSpeechService())
    list(pipeline.speak(SENTENCE, timeout=5).chunks)
    pipeline.close()

    lingering = LingeringSpeechService.lingering
    assert lingering is not None and lingering.cancelled()
    assert _tts_threads() == []
