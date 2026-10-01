"""Talking over zrb in hands-free: what stops, and where the words go."""

import asyncio

import pytest

from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import MicState, Utterance
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
        config,
        should_listen,
        keep_partial=False,
        on_state=None,
        on_barge_in=None,
        **kwargs,
    ):
        for index, text in enumerate(said):
            if is_barge_in and on_barge_in is not None:
                on_barge_in()
            yield Utterance(
                text.encode(), index, index + 0.5, is_barge_in, is_over_speech=is_barge_in
            )

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


@pytest.mark.asyncio
async def test_stop_words_are_their_own_list_not_the_deny_words(
    monkeypatch, interrupted, ui
):
    # "hold on" stops the turn; "no" is a deny word here but no stop word.
    _fake_listen(monkeypatch, "Hold on, please.", "no", "next")
    ui.is_thinking = True
    session = _session(stop_words=["hold on"], deny_words=["no"])

    assert await _replies(session, 2) == ["no", "next"]
    assert ui.cancelled == ["barge_in"]


@pytest.mark.asyncio
async def test_the_polite_words_a_stop_word_may_carry_are_configured(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "stop tolong", "stop please", "next")
    ui.is_thinking = True
    session = _session(polite_words=["tolong"])

    # "please" is no polite word here, so "stop please" is a message.
    assert await _replies(session, 2) == ["stop please", "next"]
    assert ui.cancelled == ["barge_in"]


@pytest.mark.asyncio
async def test_cancel_action_gives_up_waiting_after_the_turn_end_timeout(
    monkeypatch, interrupted
):
    class StuckUI(FakeUI):
        def cancel_current_turn(self, reason):
            self.cancelled.append(reason)  # the turn never ends

    stuck = StuckUI(is_thinking=True)
    set_session_ui(stuck)
    try:
        _fake_listen(monkeypatch, "start over")
        session = _session(barge_in_action="cancel", turn_end_timeout=0.05)
        reply = await asyncio.wait_for(_replies(session, 1), timeout=2)
        assert reply == ["start over"]
    finally:
        reset_session_ui()


@pytest.mark.asyncio
async def test_a_stop_word_while_the_turn_thinks_cancels_it_before_zrb_speaks(
    monkeypatch, interrupted, ui
):
    """Not said over zrb's voice, but over a running turn: with barge-in on,
    "stop" still cancels it instead of steering the model."""
    _fake_listen(monkeypatch, "stop", "what now", is_barge_in=False)
    ui.is_thinking = True
    session = _session(barge_in_enabled=True)

    assert await _replies(session, 1) == ["what now"]
    assert ui.cancelled == ["barge_in"]
    assert interrupted == []


@pytest.mark.asyncio
async def test_a_stop_word_while_the_turn_thinks_is_sent_with_barge_in_off(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "stop", is_barge_in=False)
    ui.is_thinking = True
    session = _session(barge_in_enabled=False)

    assert await _replies(session, 1) == ["stop"]
    assert ui.cancelled == []


@pytest.mark.asyncio
async def test_a_stop_word_with_no_turn_running_is_sent(monkeypatch, interrupted, ui):
    _fake_listen(monkeypatch, "stop", is_barge_in=False)
    session = _session(barge_in_enabled=True)

    assert await _replies(session, 1) == ["stop"]
    assert ui.cancelled == []


@pytest.mark.asyncio
async def test_push_to_talk_cancels_zrbs_voice_out_like_hands_free(monkeypatch):
    """With barge-in on, a recording made while zrb speaks gets the same echo
    cancellation as hands-free: without it, zrb's own voice was transcribed."""
    pytest.importorskip("numpy")
    echoes = []

    async def listen(config, should_listen, keep_partial=False, echo=None, **kwargs):
        echoes.append(echo)
        yield Utterance(b"run the tests", 0, 0.5)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)

    class RecordingUI(FakeUI):
        def __init__(self):
            super().__init__()
            self.inserted: list[str] = []

        def insert_input_text(self, text):
            self.inserted.append(text)

    recording_ui = RecordingUI()
    session = DictationSession(
        DictationConfig(
            backend=FakeBackend(), mode="ptt", barge_in_enabled=True, echo_canceller="none"
        ).resolve()
    )

    await session.toggle_recording({}, recording_ui)

    assert recording_ui.inserted == ["run the tests"]
    [echo] = echoes
    assert echo is not None



@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state, badge",
    [
        (MicState.LEARNING, "🔇 learning the room…"),
        (MicState.NO_ECHO_REFERENCE, "🔇 mic paused (speech not played by zrb)"),
        (MicState.PAUSED, "🔇 mic paused while speaking"),
    ],
)
async def test_the_badge_says_why_the_mic_is_deaf_over_zrb(
    monkeypatch, ui, state, badge
):
    """With barge-in on yet nothing heard over zrb, the badge tells the room
    still being learned from speech zrb cannot cancel at all."""

    async def listen(config, should_listen, on_state=None, **kwargs):
        on_state(state)
        yield Utterance(b"hello", 0, 0.5)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))

    await _replies(_session(barge_in_enabled=True), 1)

    assert badge in ui.badges
