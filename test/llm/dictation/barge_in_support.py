"""Doubles shared by the barge-in tests: a fake microphone and UI, and the
fixtures that record what reached speech and keep the judge offline."""

import asyncio

import pytest

from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import Utterance
from zrb.llm.shared.feature_config import reset_session_ui, set_session_ui


class FakeBackend(AnyDictationBackend):
    async def transcribe(self, audio: bytes) -> str:
        return audio.decode()


class FakeUI:
    """Every role accessor hands back the fake itself, as a real UI does.

    A double that answers one accessor and not another does not fail where it
    is missing: the code that reads it runs inside the dictation task, which
    catches the `AttributeError`, reports it and waits for hands-free to be
    switched on again. The test then waits for a reply that never comes.
    """

    display = property(lambda self: self)
    input = property(lambda self: self)
    session = property(lambda self: self)
    tools = property(lambda self: self)

    is_thinking = False
    is_waiting_for_answer = False
    is_turn_running = False
    pending_answer_since: float | None = None

    def __init__(self):
        self.cancelled: list[str] = []
        self.badges: list = []
        self.submitted: list = []
        self.answered: list[str] = []

    def set_status_badge(self, key, text):
        self.badges.append(text)

    def append_to_output(self, text):
        pass

    def cancel_current_turn(self, reason):
        self.cancelled.append(reason)

    def submit_message(self, text, source=None):
        self.submitted.append(text)

    def submit_answer(self, text):
        self.answered.append(text)


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


async def replies_of(session, count, timeout=10.0):
    """The first *count* replies, or a failure that names the wait.

    A missing role member raises inside the listening task, which catches it,
    reports it and goes back to waiting for hands-free to be switched on. That
    wait is unbounded, so without a bound here a one-line defect in a double
    reads as a hang: the test stalled the whole suite, and on Windows it cost
    the xdist worker. Ten seconds is far more than a fake microphone needs.
    """
    stream = session.listen_hands_free()
    replies: list[str] = []
    try:
        for _ in range(count):
            try:
                reply = await asyncio.wait_for(anext(stream), timeout)
            except TimeoutError:
                raise AssertionError(
                    f"no reply in {timeout:g}s. The dictation loop most likely "
                    "raised and reported an exception instead of speaking — see "
                    "what `_report` wrote, or run this test with `-s`."
                ) from None
            replies.append(reply.text)
        return replies
    finally:
        await stream.aclose()
