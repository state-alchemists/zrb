"""The Pipecat pipeline the capture is handed to, and the flag that turns it on.

Stage 1 of the migration (ADR-0107): the pipeline ends at a counter and decides
nothing, so what is under test is that a session opens one when the flag is set,
hands it the blocks the microphone captured, and closes it when the listening
stops — and that with the flag off, or without the extra installed, the listening
is exactly as it was.
"""

from __future__ import annotations

import pytest

from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import MicState, Utterance
from zrb.llm.util.feature_config import reset_session_ui, set_session_ui

# One captured block, as `on_captured` receives it: 16 kHz mono 16-bit PCM.
BLOCK = b"\x00\x01" * 512


class FakeBackend(AnyDictationBackend):
    """Transcribes each clip to the text it was built from."""

    async def prepare(self, report) -> None:
        return None

    async def transcribe(self, audio: bytes) -> str:
        return audio.decode()


class FakeUI:
    def __init__(self) -> None:
        self.background_tasks: set = set()
        self.outputs: list[str] = []
        self.badges: list[tuple[str, str | None]] = []

    def set_status_badge(self, key: str, text: str | None) -> None:
        self.badges.append((key, text))

    def append_to_output(self, text: str) -> None:
        self.outputs.append(text)


class FakeAudioPipeline:
    """`AudioPipeline` without a pipeline: what was started, pushed and closed."""

    made: list["FakeAudioPipeline"] = []

    def __init__(self) -> None:
        self.pushed: list[bytes] = []
        self.closed = 0

    @classmethod
    async def start(cls) -> "FakeAudioPipeline":
        made = cls()
        cls.made.append(made)
        return made

    async def push(self, chunk: bytes) -> None:
        self.pushed.append(chunk)

    async def close(self) -> None:
        self.closed += 1


def _fakes(monkeypatch, *said: bytes) -> list[bytes | None]:
    """Make the microphone capture *said*, and remember how it was handed over.

    What comes back is the `on_captured` each listening was given, so a test can
    tell a pipeline being fed from one being left out.
    """
    handed: list[bytes | None] = []

    async def listen(
        config,
        should_listen,
        keep_partial=False,
        on_state=None,
        on_barge_in=None,
        on_captured=None,
        **kwargs,
    ):
        handed.append(on_captured)
        for audio in said:
            if not should_listen():
                return
            if on_state is not None:
                on_state(MicState.HEARING)
                on_state(MicState.LISTENING)
            if on_captured is not None:
                await on_captured(BLOCK)
            yield Utterance(audio, 0, 1)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    monkeypatch.setattr("zrb.llm.dictation.feature.AudioPipeline", FakeAudioPipeline)
    return handed


def _session(**config) -> DictationSession:
    return DictationSession(
        DictationConfig(backend=FakeBackend(), mode="hands_free", **config).resolve()
    )


async def _first_reply(session: DictationSession) -> str:
    """Run hands-free until its first utterance became a reply, then stop."""
    stream = session.listen_hands_free()
    reply = await anext(stream)
    await stream.aclose()
    return reply.text


@pytest.fixture(autouse=True)
def _no_pipeline_left_over():
    FakeAudioPipeline.made = []
    yield


@pytest.mark.asyncio
async def test_the_capture_is_handed_to_the_pipeline_and_the_pipeline_closed(
    monkeypatch,
):
    monkeypatch.setattr("zrb.llm.dictation.feature.is_pipecat_available", lambda: True)
    _fakes(monkeypatch, b"hello")
    session = _session(pipecat_enabled=True)

    await _first_reply(session)

    assert len(FakeAudioPipeline.made) == 1
    pipeline = FakeAudioPipeline.made[0]
    assert pipeline.pushed == [BLOCK]
    # One for the listening that ended, not one per block.
    assert pipeline.closed == 1


@pytest.mark.asyncio
async def test_with_the_flag_off_the_capture_goes_nowhere_else(monkeypatch):
    monkeypatch.setattr("zrb.llm.dictation.feature.is_pipecat_available", lambda: True)
    handed = _fakes(monkeypatch, b"hello")
    session = _session()

    await _first_reply(session)

    assert handed == [None]
    assert FakeAudioPipeline.made == []


@pytest.mark.asyncio
async def test_without_the_extra_the_listening_goes_on_and_says_so(monkeypatch):
    ui = FakeUI()
    set_session_ui(ui)
    try:
        monkeypatch.setattr(
            "zrb.llm.dictation.feature.is_pipecat_available", lambda: False
        )
        _fakes(monkeypatch, b"hello")
        session = _session(pipecat_enabled=True)

        await _first_reply(session)
    finally:
        reset_session_ui()

    assert FakeAudioPipeline.made == []
    assert any("Pipecat is not installed" in text for text in ui.outputs)


@pytest.mark.asyncio
async def test_a_pipeline_that_will_not_start_leaves_the_listening_alone(monkeypatch):
    """A pipeline that fails is given up on, and hands-free goes on (PR #561
    review).

    The pipeline decides nothing (stage 1), so its failure must not reach the
    dictation loop's outer handler, which stops hands-free for the session.
    """
    ui = FakeUI()
    set_session_ui(ui)
    try:
        monkeypatch.setattr(
            "zrb.llm.dictation.feature.is_pipecat_available", lambda: True
        )
        _fakes(monkeypatch, b"hello")

        class BrokenPipeline:
            @classmethod
            async def start(cls):
                raise RuntimeError("Pipecat could not start")

        monkeypatch.setattr("zrb.llm.dictation.feature.AudioPipeline", BrokenPipeline)
        session = _session(pipecat_enabled=True)

        reply = await _first_reply(session)
    finally:
        reset_session_ui()

    assert reply == "hello"
    assert session.is_hands_free
    assert any("Pipecat input pipeline stopped" in text for text in ui.outputs)


@pytest.mark.asyncio
async def test_a_pipeline_that_fails_to_close_leaves_the_listening_alone(
    monkeypatch, caplog
):
    """A failure while the pipeline is torn down is the pipeline's, not the
    listening's (PR #561 review).

    `_listen` stops the pipeline in its `finally`, and a close that raised would
    reach the dictation loop's outer handler and switch hands-free off for the
    session, taking the microphone with it. Stage 1's pipeline decides nothing,
    so the failure is contained and logged instead.
    """
    ui = FakeUI()
    set_session_ui(ui)
    try:
        monkeypatch.setattr(
            "zrb.llm.dictation.feature.is_pipecat_available", lambda: True
        )
        _fakes(monkeypatch, b"hello")

        class ClosingPipeline(FakeAudioPipeline):
            async def close(self) -> None:
                raise RuntimeError("the worker will not take the cancel")

        monkeypatch.setattr("zrb.llm.dictation.feature.AudioPipeline", ClosingPipeline)
        session = _session(pipecat_enabled=True)

        reply = await _first_reply(session)
    finally:
        reset_session_ui()

    assert reply == "hello"
    assert session.is_hands_free
    assert "the worker will not take the cancel" in caplog.text


@pytest.mark.asyncio
async def test_a_pipeline_that_fails_mid_capture_is_closed_and_not_retried(monkeypatch):
    """A pipeline whose hand-over fails is closed, and no other is opened
    (PR #561 review).

    The session can run for hours, so a pipeline left alive after a push failed
    would hold its worker and its transport for the rest of it while the code
    says it stopped; and the block after it must not build another one.
    """
    ui = FakeUI()
    set_session_ui(ui)
    try:
        monkeypatch.setattr(
            "zrb.llm.dictation.feature.is_pipecat_available", lambda: True
        )
        _fakes(monkeypatch, b"hello", b"world")

        class PushFailsPipeline(FakeAudioPipeline):
            async def push(self, chunk: bytes) -> None:
                raise RuntimeError("the pipeline is gone")

        monkeypatch.setattr("zrb.llm.dictation.feature.AudioPipeline", PushFailsPipeline)
        session = _session(pipecat_enabled=True)

        stream = session.listen_hands_free()
        first = await anext(stream)
        second = await anext(stream)
        await stream.aclose()
    finally:
        reset_session_ui()

    assert (first.text, second.text) == ("hello", "world")
    assert session.is_hands_free
    # Opened once, closed when the hand-over failed, and never opened again.
    assert len(PushFailsPipeline.made) == 1
    assert PushFailsPipeline.made[0].closed == 1
    assert any("Pipecat input pipeline stopped" in text for text in ui.outputs)
