"""Talking over zrb: its voice pauses at once, then stops for words or
carries on for anything else."""

import asyncio
import contextlib

import pytest

from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.echo import EchoCancellation
from zrb.llm.dictation.feature import DictationSession
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
            yield Utterance(text.encode(), index, index + 0.5, True)

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
    assert speech == ["pause", "resume", "pause", "interrupt"]


@pytest.mark.asyncio
async def test_words_heard_while_still_speaking_stop_zrb_early(monkeypatch, speech):
    _listen(monkeypatch, "wait a moment", partials=["", "wait"])
    assert await _replies(_session(), 1) == ["wait a moment"]
    # Stopped by the partial words; the transcript finds nothing to add.
    assert speech == ["pause", "interrupt"]


@pytest.mark.asyncio
async def test_a_dropped_barge_in_lets_zrb_carry_on(monkeypatch, speech):
    _listen(monkeypatch, "hello", drop_first=True)
    assert await _replies(_session(), 1) == ["hello"]
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
async def test_the_echo_cancellation_is_built_once_with_barge_in_on(
    monkeypatch, speech
):
    seen = _listen(monkeypatch, "first")
    session = _session(barge_in="on", echo_canceller="none")
    await _replies(session, 1)
    echo = seen["echo"]
    assert isinstance(echo, EchoCancellation)
    assert echo.canceller.name == "none"

    seen2 = _listen(monkeypatch, "second")
    await _replies(session, 1)
    assert seen2["echo"] is echo


@pytest.mark.asyncio
async def test_no_echo_cancellation_with_barge_in_off(monkeypatch, speech):
    seen = _listen(monkeypatch, "first")
    await _replies(_session(barge_in="off"), 1)
    assert seen["echo"] is None


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
