"""The Pipecat pipeline the capture is handed to, and the flag that turns it on.

Stage 1 of the migration (ADR-0106): the pipeline ends at a counter and decides
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


async def _first_reply(session: DictationSession) -> None:
    """Run hands-free until its first utterance became a reply, then stop."""
    stream = session.listen_hands_free()
    await anext(stream)
    await stream.aclose()


@pytest.fixture(autouse=True)
def _no_pipeline_left_over():
    FakeAudioPipeline.made = []
    yield


@pytest.mark.asyncio
async def test_the_capture_is_handed_to_the_pipeline_and_the_pipeline_closed(
    monkeypatch,
):
    monkeypatch.setattr("zrb.llm.dictation.feature.is_pipecat_available", lambda: True)
    handed = _fakes(monkeypatch, b"hello")
    session = _session(pipecat_enabled=True)

    await _first_reply(session)

    assert len(FakeAudioPipeline.made) == 1
    pipeline = FakeAudioPipeline.made[0]
    assert pipeline.pushed == [BLOCK]
    # One for the listening that ended, not one per block.
    assert pipeline.closed == 1
    assert handed == [pipeline.push]


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
        handed = _fakes(monkeypatch, b"hello")
        session = _session(pipecat_enabled=True)

        await _first_reply(session)
    finally:
        reset_session_ui()

    assert handed == [None]
    assert FakeAudioPipeline.made == []
    assert any("Pipecat is not installed" in text for text in ui.outputs)
