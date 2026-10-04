"""Talking over zrb: its voice pauses at once, then stops for words or
carries on for anything else."""

import asyncio
import contextlib

import pytest

from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.interrupt_judge import BargeInVerdict
from zrb.llm.dictation.listen import Utterance
from zrb.llm.util.feature_config import reset_session_ui, set_session_ui


class FakeBackend(AnyDictationBackend):
    async def transcribe(self, audio: bytes) -> str:
        return audio.decode()


class FakeUI:
    is_thinking = False
    is_waiting_for_answer = False

    def __init__(self):
        self.cancelled: list[str] = []
        self.badges: list = []

    def set_status_badge(self, key, text):
        self.badges.append(text)

    def append_to_output(self, text):
        pass

    def cancel_current_turn(self, reason):
        self.cancelled.append(reason)


@pytest.fixture
def speech(monkeypatch):
    """What reached speech, in order."""
    events: list[str] = []
    for name in ("pause", "resume", "interrupt"):
        monkeypatch.setattr(
            f"zrb.llm.dictation.feature.{name}_speech",
            lambda key, name=name: events.append(name),
        )
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))
    fake = FakeUI()
    set_session_ui(fake)
    yield events
    reset_session_ui()


@pytest.fixture(autouse=True)
def judge(monkeypatch):
    """The interrupt judge, offline: it could not answer, so the word lists
    decide — which is what happens with no small model reachable. A test that
    wants a verdict patches over this."""

    async def could_not_answer(command, model=None):
        return None

    monkeypatch.setattr(
        "zrb.llm.dictation.interrupt_judge.judge_barge_in", could_not_answer
    )


def _listen(monkeypatch, *heard, partials=(), drop_first=False):
    """The microphone hears *heard* over zrb, one utterance each; *partials*
    are shown while the first is spoken; with *drop_first*, a barge-in is
    reported and then dropped before them."""
    seen: dict = {}

    async def listen(config, should_listen, on_barge_in=None, **kwargs):
        seen.update(kwargs, config=config)
        if drop_first:
            on_barge_in()
            kwargs["on_barge_in_dropped"]()
        for index, text in enumerate(heard):
            on_barge_in()
            if index == 0:
                for partial in partials:
                    kwargs["on_partial"](partial)
            yield Utterance(
                text.encode(), index, index + 0.5, True, is_over_speech=True
            )

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    return seen


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
async def test_words_over_zrb_pause_it_then_stop_it(monkeypatch, speech):
    _listen(monkeypatch, "use pytest instead")
    assert await _replies(_session(), 1) == ["use pytest instead"]
    assert speech == ["pause", "interrupt"]


@pytest.mark.asyncio
async def test_nothing_intelligible_over_zrb_lets_it_carry_on(monkeypatch, speech):
    _listen(monkeypatch, "", "go on")
    assert await _replies(_session(), 1) == ["go on"]
    assert speech == ["pause", "resume", "pause", "interrupt"]


@pytest.mark.asyncio
async def test_words_without_the_wake_word_let_zrb_carry_on(monkeypatch, speech):
    _listen(monkeypatch, "just chatting", "hey zed stop now")
    assert await _replies(_session(wake_words=["hey zed"]), 1) == ["stop now"]
    # Talk that is not the user's held zrb, and gave it back.
    assert speech == ["pause", "resume", "pause", "interrupt"]


@pytest.mark.asyncio
async def test_the_wake_word_heard_while_still_speaking_stops_zrb_early(
    monkeypatch, speech
):
    _listen(monkeypatch, "hey zed wait there", partials=["", "hey zed"])
    assert await _replies(_session(wake_words=["hey zed"]), 1) == ["wait there"]
    # Held on loudness, then stopped by the wake word in the live words; the
    # transcript then finds nothing left to add.
    assert speech == ["pause", "interrupt"]


@pytest.mark.asyncio
async def test_with_wake_words_talk_not_meant_for_zrb_is_held_and_given_back(
    monkeypatch, speech
):
    """Held on loudness before anything is known, because being talked over is
    worse than a hold taken for zrb's own voice. The words then give that hold
    back — twice here, once for words meant for nobody and once for the
    transcriber guessing — so zrb never talks through an interruption."""
    _listen(monkeypatch, "sleep well", "and this and this", "hey zed go on")
    ui = FakeUI()
    set_session_ui(ui)

    assert await _replies(_session(wake_words=["hey zed"]), 1) == ["go on"]
    assert speech == ["pause", "resume", "pause", "resume", "pause", "interrupt"]
    assert "✋ paused · listening…" in ui.badges


@pytest.mark.asyncio
async def test_words_a_word_list_cannot_read_as_a_stop_stop_zrb_anyway(
    monkeypatch, speech
):
    """A stop word said alone is exact and free; "please fucking stop" is not,
    and no word list should have to know that. The small model reads it, and
    the turn is cancelled rather than reaching the model as a message."""

    async def judge_stop(command, model=None):
        if command == "please fucking stop":
            return BargeInVerdict(intent="stop", reason="asks zrb to be quiet")
        return None

    monkeypatch.setattr("zrb.llm.dictation.interrupt_judge.judge_barge_in", judge_stop)
    ui = FakeUI()
    set_session_ui(ui)
    _listen(monkeypatch, "hey zed please fucking stop", "hey zed go on")

    assert await _replies(_session(wake_words=["hey zed"]), 1) == ["go on"]
    assert ui.cancelled == ["barge_in"]
    assert speech == ["pause", "interrupt", "pause", "interrupt"]


@pytest.mark.asyncio
async def test_a_stop_word_is_not_put_to_the_model(monkeypatch, speech):
    """The word lists answer first, for free: the model is asked about what
    they could not read, and about nothing else."""
    asked: list[str] = []

    async def judge_spy(command, model=None):
        asked.append(command)
        return None

    monkeypatch.setattr("zrb.llm.dictation.interrupt_judge.judge_barge_in", judge_spy)
    _listen(monkeypatch, "hey zed stop", "hey zed go on")

    assert await _replies(_session(wake_words=["hey zed"]), 1) == ["go on"]
    assert asked == ["go on"]
    assert speech == ["pause", "interrupt", "pause", "interrupt"]


@pytest.mark.asyncio
async def test_a_stop_said_twice_with_a_wake_word_is_not_transcriber_noise(
    monkeypatch, speech
):
    """One phrase said twice reads as a transcriber guessing at noise — but a
    wake word in front of it is someone saying stop again, and saying it again
    is what someone does when the first went unheard."""
    _listen(monkeypatch, "hey zed stop, hey zed stop", "hey zed go on")

    assert await _replies(_session(wake_words=["hey zed"]), 2) == [
        "stop, hey zed stop",
        "go on",
    ]


@pytest.mark.asyncio
async def test_a_partial_guess_for_a_cough_does_not_stop_zrb(monkeypatch, speech):
    """Without wake words the transcript decides: a streaming recognizer
    guesses "the" for a cough, and zrb, paused meanwhile, carries on."""
    _listen(monkeypatch, "", "go on", partials=["the"])
    assert await _replies(_session(), 1) == ["go on"]
    assert speech == ["pause", "resume", "pause", "interrupt"]


@pytest.mark.asyncio
async def test_the_badge_comes_back_when_zrb_carries_on(monkeypatch, speech):
    _listen(monkeypatch, "", "go on")
    ui = FakeUI()
    set_session_ui(ui)

    await _replies(_session(), 1)

    paused = ui.badges.index("✋ paused · listening…")
    assert "🎤 listening" in ui.badges[paused:]


@pytest.mark.asyncio
async def test_stop_said_too_briefly_to_pause_zrb_still_stops_it(monkeypatch, speech):
    """A crisp "stop" is shorter than barge_in_min_speech: nothing paused
    zrb, but it was said over it, so it stops zrb and cancels the turn
    rather than reaching the model as a message."""
    ui = FakeUI()
    set_session_ui(ui)

    async def listen(config, should_listen, **kwargs):
        yield Utterance(b"stop", 0, 0.3, is_over_speech=True)
        yield Utterance(b"carry on", 1, 1.5)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    assert await _replies(_session(), 1) == ["carry on"]
    assert speech == ["interrupt"]
    assert ui.cancelled == ["barge_in"]


@pytest.mark.asyncio
async def test_a_dropped_barge_in_lets_zrb_carry_on(monkeypatch, speech):
    _listen(monkeypatch, "hello there", drop_first=True)
    assert await _replies(_session(), 1) == ["hello there"]
    assert speech == ["pause", "resume", "pause", "interrupt"]


@pytest.mark.asyncio
async def test_closing_mid_pause_resumes(monkeypatch, speech):
    session = _session()

    async def listen(config, should_listen, on_barge_in=None, **kwargs):
        on_barge_in()
        session.close()
        return
        yield

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    stream = session.listen_hands_free()
    task = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
        await task
    # Closed here, not by the garbage collector during a later test.
    await stream.aclose()
    assert speech[:2] == ["pause", "resume"]


@pytest.mark.asyncio
async def test_switching_hands_free_off_resumes_paused_speech(monkeypatch, speech):
    session = _session(hands_free_commands=["/handsfree"])
    heard = asyncio.Event()

    async def listen(config, should_listen, on_barge_in=None, **kwargs):
        on_barge_in()  # the user started talking over zrb...
        heard.set()
        await asyncio.Event().wait()  # ...and is still talking
        yield

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    stream = session.listen_hands_free()
    task = asyncio.ensure_future(anext(stream))
    await asyncio.wait_for(heard.wait(), 1)

    [command] = [c for c in session.create_commands() if c.command == "/handsfree"]
    command.handle({}, None)

    assert speech == ["pause", "resume"]
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
        await task
    await stream.aclose()


@pytest.mark.asyncio
async def test_a_broken_microphone_mid_barge_in_resumes_speech(monkeypatch, speech):
    session = _session()

    async def listen(config, should_listen, on_barge_in=None, **kwargs):
        on_barge_in()
        raise OSError("microphone unplugged")
        yield

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    stream = session.listen_hands_free()
    task = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
        await task
    await stream.aclose()

    assert speech[:2] == ["pause", "resume"]
    assert not session.is_hands_free
