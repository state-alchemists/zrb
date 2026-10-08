"""Pin Pipecat TTS delivery, serialization, interruption, and cleanup."""

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

RATE = 24000

CHUNK = b"\x11\x22" * 400

SENTENCE = "the tests are green"


class FakeSpeechService(TTSService):
    """A local-style service that returns start, audio, and stop frames."""

    def __init__(self, chunks: int = 1, delay: float = 0.0) -> None:
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
                return
            yield TTSAudioRawFrame(
                audio=CHUNK, sample_rate=RATE, num_channels=1, context_id=context_id
            )

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, InterruptionFrame):
            self.interruptions += 1
        await super().process_frame(frame, direction)


class RaisingSpeechService(FakeSpeechService):
    """A service whose synthesis fails."""

    async def run_tts(self, text: str, context_id: str):
        self.said.append(text)
        if text:
            raise RuntimeError("the model is unhappy")
        yield TTSAudioRawFrame(
            audio=CHUNK, sample_rate=RATE, num_channels=1, context_id=context_id
        )


class TaggedSpeechService(FakeSpeechService):
    """A fake service whose chunks identify their source sentence."""

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
    """Return this process's TTS pipeline threads."""
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
    """The service's sentence and sample rate reach playback unchanged."""
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
    """A long-lived pipeline reuses its service for the next sentence."""
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
    """The second sentence waits until the first is read to completion."""
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
        assert list(first.chunks) == [CHUNK]
        assert is_said.wait(5)
    finally:
        pipeline.close()

    assert said_second == [[CHUNK]]


def test_dropping_a_sentence_ends_the_read_at_once_and_the_synthesis_with_it():
    """Closing audio stops reading and interrupts synthesis before the next sentence."""
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
    """Even a failed interruption releases the sentence lock for the next call."""
    service = FakeSpeechService()
    pipeline = TTSPipeline.start(service)

    def refused(loop, coroutine, timeout=None):
        coroutine.close()
        raise ValueError("the service refused the interruption")

    try:
        audio = pipeline.speak(SENTENCE, timeout=5)
        assert next(iter(audio.chunks)) == CHUNK  # read, but not to its end

        with monkeypatch.context() as failing:
            failing.setattr(pipecat_tts, "_call", refused)
            try:
                audio.close()
            except ValueError:
                pass

        said: "list[list[bytes]]" = []
        is_said = threading.Event()

        def say_next() -> None:
            said.append(list(pipeline.speak(SENTENCE, timeout=5).chunks))
            is_said.set()

        threading.Thread(target=say_next, daemon=True).start()
        assert is_said.wait(5), "the sentence after a failed interruption never started"
    finally:
        pipeline.close()

    assert said == [[CHUNK]]
    assert service.said == [SENTENCE, SENTENCE]


def test_a_service_that_cannot_say_the_sentence_is_reported_before_it_is_played():
    """Synthesis failure is raised before partial audio is played."""
    service = RaisingSpeechService()
    pipeline = TTSPipeline.start(service)
    try:
        with pytest.raises(RuntimeError):
            pipeline.speak(SENTENCE, timeout=5)
    finally:
        pipeline.close()

    assert service.said == [SENTENCE]


def test_a_sentence_that_never_arrives_tells_the_service_to_stop():
    """A timed-out sentence is dropped and tells the service to stop."""
    service = FakeSpeechService(chunks=1, delay=0.5)
    pipeline = TTSPipeline.start(service)
    try:
        with pytest.raises(RuntimeError, match="said nothing"):
            pipeline.speak(SENTENCE, timeout=0.05)
        assert _wait_until(lambda: service.interruptions == 1)
    finally:
        pipeline.close()


def test_audio_from_a_sentence_that_timed_out_is_not_played_as_the_next_one():
    """Timed-out audio is interrupted rather than delivered under the next sentence."""
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
    """Closing stops the loop thread and remains safe when repeated."""
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
