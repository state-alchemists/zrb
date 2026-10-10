"""Talking over zrb in hands-free: what stops, and where the words go."""

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
                text.encode(),
                index,
                index + 0.5,
                is_barge_in,
                is_over_speech=is_barge_in,
            )

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))


def _session(**config) -> DictationSession:
    # The judge asks a real small model about an ambiguous utterance.
    config.setdefault("interrupt_judge_enabled", False)
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
    _fake_listen(monkeypatch, "Hold on.", "no", "what next")
    ui.is_thinking = True
    session = _session(stop_words=["hold on"], deny_words=["no"])

    assert await _replies(session, 2) == ["no", "what next"]
    assert ui.cancelled == ["barge_in"]


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
async def test_the_badge_says_when_the_mic_is_deaf_over_zrb(monkeypatch, ui):
    async def listen(config, should_listen, on_state=None, **kwargs):
        on_state(MicState.PAUSED)
        yield Utterance(b"hello", 0, 0.5)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))

    await _replies(_session(), 1)

    assert "🔇 mic paused while speaking" in ui.badges


@pytest.mark.asyncio
async def test_a_single_word_over_zrb_is_not_taken_for_the_user(
    monkeypatch, interrupted, ui
):
    """zrb's own voice and noise come through as a word or two ("sleep",
    "yeah"); over zrb it takes two words, so zrb carries on."""
    _fake_listen(monkeypatch, "sleep", "use pytest")
    session = _session()

    assert await _replies(session, 1) == ["use pytest"]
    assert any("too few words to interrupt" in str(badge) for badge in ui.badges)


@pytest.mark.asyncio
async def test_a_single_word_while_a_turn_runs_does_not_steer_it(
    monkeypatch, interrupted, ui
):
    """With barge-in on, talking while a turn runs interrupts it as talking
    over zrb does, so the same two-word minimum keeps noise out."""
    _fake_listen(monkeypatch, "sleep", "use pytest", is_barge_in=False)
    ui.is_thinking = True
    session = _session(barge_in_enabled=True)

    assert await _replies(session, 1) == ["use pytest"]
    assert any("too few words to interrupt" in str(badge) for badge in ui.badges)
    assert ui.cancelled == []


@pytest.mark.asyncio
async def test_a_single_word_while_a_turn_runs_is_sent_with_barge_in_off(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "sleep", is_barge_in=False)
    ui.is_thinking = True
    session = _session(barge_in_enabled=False)

    assert await _replies(session, 1) == ["sleep"]


@pytest.mark.asyncio
async def test_a_single_word_with_no_turn_running_is_sent(monkeypatch, interrupted, ui):
    _fake_listen(monkeypatch, "hello", is_barge_in=False)
    session = _session(barge_in_enabled=True)

    assert await _replies(session, 1) == ["hello"]


@pytest.mark.asyncio
async def test_a_stray_word_does_not_open_a_turn_when_more_are_asked_for(
    monkeypatch, interrupted, ui
):
    """A public place: `min_words` keeps a stranger's one word from becoming a
    turn, while a real request still gets through."""
    _fake_listen(monkeypatch, "hello", "run the tests", is_barge_in=False)
    session = _session(min_words=2)

    assert await _replies(session, 1) == ["run the tests"]
    assert any("too few words" in str(badge) for badge in ui.badges)


@pytest.mark.asyncio
async def test_an_answer_is_never_too_short_to_be_a_message(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "later", is_barge_in=False)
    ui.is_waiting_for_answer = True

    assert await _replies(_session(min_words=2), 1) == ["later"]


@pytest.mark.asyncio
async def test_a_stop_word_is_never_too_short_to_be_a_message(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "wait", is_barge_in=False)

    assert await _replies(_session(min_words=3), 1) == ["wait"]
    assert ui.cancelled == []


@pytest.mark.asyncio
async def test_a_polite_answer_is_an_answer_and_is_never_too_short(
    monkeypatch, interrupted, ui
):
    """PR #561 review: a yes or a no may carry a polite word, so `min_words`
    cannot drop "yes please" before the approval it answers is read."""
    _fake_listen(monkeypatch, "yes please", is_barge_in=False)
    session = _session(min_words=3, approve_words=["yes"])

    stream = session.listen_hands_free()
    reply = await anext(stream)
    await stream.aclose()

    assert reply.text == "yes please"
    assert reply.approval == "yes"


@pytest.mark.asyncio
async def test_a_single_word_answers_a_prompt_while_a_turn_runs(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "later", is_barge_in=False)
    ui.is_thinking = True
    ui.is_waiting_for_answer = True
    session = _session(barge_in_enabled=True)

    assert await _replies(session, 1) == ["later"]


@pytest.mark.asyncio
async def test_a_single_stop_word_or_answer_over_zrb_still_counts(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "wait", "yes")
    ui.is_thinking = True
    session = _session(approve_words=["yes"])

    assert await _replies(session, 1) == ["yes"]
    assert ui.cancelled == ["barge_in"]


@pytest.mark.asyncio
async def test_a_single_word_answers_a_pending_prompt_over_zrb(monkeypatch, ui):
    _fake_listen(monkeypatch, "later")
    ui.is_waiting_for_answer = True

    assert await _replies(_session(), 1) == ["later"]


@pytest.mark.asyncio
async def test_the_transcriber_guessing_at_noise_is_dropped(
    monkeypatch, interrupted, ui
):
    _fake_listen(monkeypatch, "and this and this", "Thank you.", "run the tests")

    assert await _replies(_session(), 1) == ["run the tests"]
    assert any("guessing at noise" in str(badge) for badge in ui.badges)


@pytest.mark.asyncio
async def test_no_no_is_meant_however_repetitive(monkeypatch, interrupted, ui):
    _fake_listen(monkeypatch, "no no")
    ui.is_thinking = True

    replies = _session(stop_words=[], deny_words=["no"]).listen_hands_free()
    assert (await anext(replies)).text == "no no"
    await replies.aclose()
