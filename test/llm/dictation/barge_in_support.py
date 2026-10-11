"""Doubles shared by the barge-in tests: a fake microphone and UI, and the
fixtures that record what reached speech and keep the judge offline."""

import pytest

from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import Utterance
from zrb.llm.util.feature_config import reset_session_ui, set_session_ui


class FakeBackend(AnyDictationBackend):
    async def transcribe(self, audio: bytes) -> str:
        return audio.decode()


class FakeUI:
    is_thinking = False
    is_waiting_for_answer = False
    is_turn_running = False

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

    async def could_not_answer(command, model=None, timeout=None):
        return None

    monkeypatch.setattr(
        "zrb.llm.dictation.interrupt_judge.judge_barge_in", could_not_answer
    )


def listen_over_zrb(monkeypatch, *heard, partials=(), drop_first=False):
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


def make_session(**config) -> DictationSession:
    return DictationSession(
        DictationConfig(backend=FakeBackend(), mode="hands_free", **config).resolve()
    )


async def replies_of(session, count):
    stream = session.listen_hands_free()
    replies = [(await anext(stream)).text for _ in range(count)]
    await stream.aclose()
    return replies
