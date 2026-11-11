"""A turn written in more than one response.

A turn with a tool call is several model responses, and the claim deciding what
the stop hook reads was made by the turn rather than by the response that last
spoke: a block said before the tool call silenced every answer written after it,
including the turn's last word. These tests pin the claim to one response.
"""

from types import SimpleNamespace

import pytest

from zrb.llm.hook.contracts.interface import HookContext
from zrb.llm.hook.contracts.types import HookEvent
from zrb.llm.speech import SpeechConfig
from zrb.llm.speech.feature import SpeechSession


class FakeSpeaker:
    def __init__(self):
        self.said: list[str] = []
        self.is_enabled = True

    def say(self, text, is_stale=None, voice="", cut_when_stale=True):
        self.said.append(text)

    def clear(self):
        pass

    def interrupt(self):
        pass

    def close(self):
        pass


def _session(**config) -> SpeechSession:
    config.setdefault("enabled", True)
    session = SpeechSession(SpeechConfig(**config).resolve())
    session.speaker = FakeSpeaker()  # type: ignore[assignment]
    return session


def _stop(message: str) -> HookContext:
    return HookContext(
        event=HookEvent.STOP, event_data={}, last_assistant_message=message
    )


def _text(content: str):
    """A new response whose first part, and only part, is this text."""
    return SimpleNamespace(
        event_kind="part_start",
        index=0,
        part=SimpleNamespace(part_kind="text", content=content),
    )


def _delta(content: str):
    return SimpleNamespace(
        event_kind="part_delta",
        delta=SimpleNamespace(part_delta_kind="text", content_delta=content),
    )


def _tool_call():
    return SimpleNamespace(
        event_kind="part_start", part=SimpleNamespace(part_kind="tool-call")
    )


@pytest.mark.asyncio
async def test_the_answer_written_after_a_spoken_block_is_read_at_stop():
    """The block before the tool call was heard; the answer after it was not, and
    no block marks it — so Stop has to read it. It is the answer to the turn, and
    the whole turn went unspoken without it."""
    session = _session(stream=True)
    answer = "The parser had one bug. It is fixed now."

    session.handle_stream_event(_text("<spoken>Let me check the file.</spoken>"))
    session.handle_stream_event(_tool_call())
    session.handle_stream_event(_text(""))
    session.handle_stream_event(_delta(answer))

    await session.handle_stop(_stop(answer))

    assert session.speaker.said == ["Let me check the file.", answer]


@pytest.mark.asyncio
async def test_the_response_that_spoke_its_block_is_not_read_again():
    """The other half of the claim: a last response whose block was said is
    streaming's, so Stop leaves it alone rather than saying it twice."""
    session = _session(stream=True)
    reply = "<spoken>Let me check the file.</spoken>"

    session.handle_stream_event(_text(reply))
    session.handle_stream_event(_tool_call())

    await session.handle_stop(_stop(reply))

    assert session.speaker.said == ["Let me check the file."]
