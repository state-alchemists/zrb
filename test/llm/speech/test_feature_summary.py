"""A reply longer than ``summarize_above_chars`` is spoken as a summary."""

import threading
from types import SimpleNamespace

import pytest

from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.types import HookEvent
from zrb.llm.speech import SpeechConfig
from zrb.llm.speech.feature import SpeechSession
from zrb.llm.speech.summary import SpeechSummaryError

LONG = "The change touches three modules and adds a new knob. " * 6


class FakeSpeaker:
    def __init__(self):
        self.said: list[str] = []
        self.is_enabled = True

    def say(self, text, is_stale=None):
        self.said.append(text)

    def say_later(self, produce):
        # The real speaker calls it from a thread of its own, with no loop.
        thread = threading.Thread(target=lambda: self.said.append(produce()))
        thread.start()
        thread.join()

    def clear(self):
        pass

    def interrupt(self):
        pass

    def close(self):
        pass


def _session(**config) -> SpeechSession:
    session = SpeechSession(SpeechConfig(enabled=True, **config).resolve())
    session.speaker = FakeSpeaker()
    return session


def _stop(message: str) -> HookContext:
    return HookContext(
        event=HookEvent.STOP, event_data={}, last_assistant_message=message
    )


def _text_delta(content: str):
    return SimpleNamespace(
        event_kind="part_delta",
        delta=SimpleNamespace(part_delta_kind="text", content_delta=content),
    )


@pytest.fixture
def summarizer(monkeypatch):
    calls = []

    async def summarize(text, model, timeout):
        calls.append((text, model, timeout))
        return "Three modules changed."

    monkeypatch.setattr("zrb.llm.speech.feature.summarize_for_speech", summarize)
    return calls


@pytest.mark.asyncio
async def test_a_long_reply_is_spoken_as_its_summary(summarizer):
    session = _session(
        stream=False,
        summarize_above_chars=100,
        summary_model="some:model",
        summary_timeout=3,
    )

    await session.handle_stop(_stop(LONG))

    assert session.speaker.said == ["Three modules changed."]
    assert summarizer == [(LONG.strip(), "some:model", 3)]


@pytest.mark.asyncio
async def test_a_short_reply_is_read_whole(summarizer):
    session = _session(stream=False, summarize_above_chars=1000)

    await session.handle_stop(_stop("Done."))

    assert session.speaker.said == ["Done."]
    assert summarizer == []


@pytest.mark.asyncio
async def test_a_reply_is_read_whole_when_the_knob_is_off(summarizer):
    session = _session(stream=False, summarize_above_chars=0)

    await session.handle_stop(_stop(LONG))

    assert session.speaker.said == [LONG.strip()]
    assert summarizer == []


@pytest.mark.asyncio
async def test_the_reply_is_not_streamed_while_summarizing(summarizer):
    session = _session(stream=True, summarize_above_chars=100)

    session.handle_stream_event(_text_delta("A whole sentence is here now. "))
    assert session.speaker.said == []
    await session.handle_stop(_stop(LONG))

    assert session.speaker.said == ["Three modules changed."]


@pytest.mark.asyncio
async def test_a_failed_summary_leaves_the_reply_read_whole(monkeypatch):
    async def fail(text, model, timeout):
        raise SpeechSummaryError("down")

    monkeypatch.setattr("zrb.llm.speech.feature.summarize_for_speech", fail)
    session = _session(stream=False, summarize_above_chars=100)

    await session.handle_stop(_stop(LONG))

    assert session.speaker.said == [LONG.strip()]
