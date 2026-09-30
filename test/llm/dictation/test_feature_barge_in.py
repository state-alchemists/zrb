"""Talking over zrb in hands-free: what stops, and where the words go."""

import asyncio

import pytest

from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import Utterance
from zrb.llm.util.feature_config import reset_session_ui, set_session_ui


class FakeBackend(AnyDictationBackend):
    async def transcribe(self, audio: bytes) -> str:
        return audio.decode()


class FakeUI:
    def __init__(self, is_thinking=False, is_waiting_for_answer=False):
        self.is_thinking = is_thinking
        self.is_waiting_for_answer = is_waiting_for_answer
        self.cancelled: list[str] = []
        self.badges: list = []

    def set_status_badge(self, key, text):
        self.badges.append(text)

    def append_to_output(self, text):
        pass

    def cancel_current_turn(self, reason):
        self.cancelled.append(reason)
        self.is_thinking = False


@pytest.fixture
def interrupted(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "zrb.llm.dictation.feature.interrupt_speech", lambda key: calls.append(key)
    )
    return calls


@pytest.fixture
def ui():
    fake = FakeUI()
    set_session_ui(fake)
    yield fake
    reset_session_ui()


def _fake_listen(monkeypatch, *said: str, is_barge_in=True):
    async def listen(
        config, should_listen, keep_partial=False, on_state=None, on_barge_in=None
    ):
        for index, text in enumerate(said):
            if is_barge_in and on_barge_in is not None:
                on_barge_in()
            yield Utterance(text.encode(), index, index + 0.5, is_barge_in)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))


def _session(**config) -> DictationSession:
    return DictationSession(
        DictationConfig(backend=FakeBackend(), mode="hands_free", **config).resolve()
    )


async def _replies(session, count):
    stream = session.listen_hands_free()
    replies = [(await anext(stream)).text for _ in range(count)]
    await stream.aclose()
    return replies


@pytest.mark.asyncio
async def test_talking_over_zrb_stops_its_speech_and_steers_the_turn(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "also update the docs")
    ui.is_thinking = True
    session = _session()

    assert await _replies(session, 1) == ["also update the docs"]
    assert len(interrupted) == 1
    assert ui.cancelled == []


@pytest.mark.asyncio
async def test_a_lone_stop_word_cancels_the_turn_and_is_sent_nowhere(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "Stop!", "what now")
    ui.is_thinking = True
    session = _session()

    assert await _replies(session, 1) == ["what now"]
    assert ui.cancelled == ["barge_in"]


@pytest.mark.asyncio
async def test_cancel_action_stops_the_turn_before_sending_what_was_said(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "do it differently")
    ui.is_thinking = True
    session = _session(barge_in_action="cancel")

    assert await _replies(session, 1) == ["do it differently"]
    assert ui.cancelled == ["barge_in"]


@pytest.mark.asyncio
async def test_cancel_action_waits_for_the_turn_to_unwind(monkeypatch, interrupted):
    class SlowUI(FakeUI):
        def cancel_current_turn(self, reason):
            self.cancelled.append(reason)
            asyncio.get_running_loop().call_later(0.1, self._finish)

        def _finish(self):
            self.is_thinking = False

    slow = SlowUI(is_thinking=True)
    set_session_ui(slow)
    try:
        _fake_listen(monkeypatch, "start over")
        session = _session(barge_in_action="cancel")
        assert await _replies(session, 1) == ["start over"]
        assert slow.is_thinking is False
    finally:
        reset_session_ui()


@pytest.mark.asyncio
async def test_no_to_a_pending_approval_denies_it_rather_than_the_turn(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "No.")
    ui.is_waiting_for_answer = True
    session = _session()

    assert await _replies(session, 1) == ["No."]
    assert ui.cancelled == []


@pytest.mark.asyncio
async def test_with_wake_words_speech_is_stopped_only_once_one_is_heard(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "just chatting", "hey zed stop", "hey zed go on")
    session = _session(wake_words=["hey zed"])

    assert await _replies(session, 1) == ["go on"]
    assert len(interrupted) == 2  # "stop" and "go on", never "just chatting"
    assert ui.cancelled == ["barge_in"]


@pytest.mark.asyncio
async def test_speech_after_zrb_stopped_is_an_ordinary_turn(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "stop", is_barge_in=False)
    session = _session()

    assert await _replies(session, 1) == ["stop"]
    assert interrupted == []
    assert ui.cancelled == []
