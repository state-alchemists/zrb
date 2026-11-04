"""One whole turn, through the real runner: is the reply spoken at Stop?

Speech's two paths are covered separately (a Stop hook with a message, and a
stream of events), but nothing drives both through `run_agent`, which is where
they meet the pool thread the hooks actually run on.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic_ai import AgentRunResultEvent

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.manager import HookManager
from zrb.llm.speech import SpeechConfig
from zrb.llm.speech.feature import SpeechSession
from zrb.llm.stream_observer import create_observed_event_handler

REPLY = "The wardrobe is pushed. Two things I noticed while checking."


class FakeSpeaker:
    is_playing_in_process = True

    def __init__(self):
        self.said: list[str] = []
        self.is_enabled = True
        self.volume = 100

    def say(self, text, is_stale=None, voice="", cut_when_stale=True):
        self.said.append(text)

    def interrupt(self):
        self.said.append("<interrupted>")

    def set_volume(self, percent):
        self.volume = percent

    def clear(self):
        pass

    def close(self):
        pass

    def restart_backends(self):
        pass


def _agent(reply: str) -> MagicMock:
    """An agent whose run streams *reply* as text parts, then returns it."""

    async def fake_run(*args, **kwargs):
        handler = kwargs.pop("event_stream_handler", None)
        result = MagicMock()
        result.output = reply
        result.all_messages.return_value = []

        async def events():
            yield SimpleNamespace(
                event_kind="part_start",
                index=0,
                part=SimpleNamespace(part_kind="text", content=""),
            )
            step = 12
            for start in range(0, len(reply), step):
                yield SimpleNamespace(
                    event_kind="part_delta",
                    index=0,
                    delta=SimpleNamespace(
                        part_delta_kind="text",
                        content_delta=reply[start : start + step],
                    ),
                )
            yield AgentRunResultEvent(result=result)

        if handler is not None:
            await handler(MagicMock(), events())
        else:
            async for _ in events():
                pass
        return result

    agent = MagicMock()
    agent.run = fake_run
    return agent


def _session() -> "tuple[SpeechSession, FakeSpeaker]":
    session = SpeechSession(SpeechConfig(enabled=True, stream=True).resolve())
    speaker = FakeSpeaker()
    session.speaker = speaker  # type: ignore[assignment]
    return session, speaker


async def _run_turn(session: SpeechSession, reply: str = REPLY):
    manager = HookManager(search_dirs=[])
    session.register_hooks(manager)
    # The way a task wires it: speech is an observer, so the UI's own handler
    # (none here) and the observer share one async event handler.
    return await run_agent(
        agent=_agent(reply),
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
        event_handler=create_observed_event_handler(
            None, [session.handle_stream_event]
        ),
    )


@pytest.mark.asyncio
async def test_a_blockless_reply_is_read_whole_when_the_turn_ends():
    session, speaker = _session()

    await _run_turn(session)

    assert speaker.said == [REPLY]


@pytest.mark.asyncio
async def test_a_spoken_block_is_read_while_it_streams_and_not_again():
    session, speaker = _session()
    block = f"<spoken>{REPLY}</spoken>\n\n```\nrunner.py:880\n```"

    await _run_turn(session, block)

    assert speaker.said == [
        "The wardrobe is pushed.",
        "Two things I noticed while checking.",
    ]


@pytest.mark.asyncio
async def test_a_hush_before_the_turn_does_not_silence_the_reply():
    """A message submitted between turns hushes speech (`interrupt_speech`),
    and that hush muted a response which was already over. Nothing of this
    turn's reply was ever said, so Stop must read it — this is the bug that
    made every reply without a `<spoken>` block go unspoken."""
    session, speaker = _session()
    session.interrupt()
    speaker.said.clear()

    await _run_turn(session)

    assert speaker.said == [REPLY]
