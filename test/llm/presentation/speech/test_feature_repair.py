"""A reply that needed a block and opened none is spoken as a line, not read.

The rule is prose in the prompt and nothing enforces it at the source — an
output type cannot be required without losing the streaming that speaks a reply
while it is written. So the repair is at the other end: one small-model call at
the end of the turn, and the listener hears the answer instead of a table.
"""

import pytest

from zrb.llm.capabilities.hook.contracts.interface import HookContext
from zrb.llm.capabilities.hook.contracts.types import HookEvent
from zrb.llm.presentation.speech import SpeechConfig, feature
from zrb.llm.presentation.speech.feature import SpeechSession
from zrb.llm.presentation.speech.repair import RepairedSpeech, SpeechRepairError

TABLE = "Where things stand:\n\n| item | cost |\n| --- | --- |\n| a | 1 |\n"
LONG = "A long enough answer. " * 20
REPAIRED = "Three modules changed and one new knob was added."


class FakeSpeaker:
    def __init__(self):
        self.said: list[str] = []
        self.voices: list[str] = []
        self.is_enabled = True

    def say(self, text, is_stale=None, voice="", cut_when_stale=True):
        self.said.append(text)
        self.voices.append(voice)

    def clear(self):
        pass

    def interrupt(self):
        pass

    def restart_backends(self):
        pass

    def close(self):
        pass


def _session(**config) -> SpeechSession:
    config.setdefault("enabled", True)
    config.setdefault("events", ["reply"])
    session = SpeechSession(SpeechConfig(**config).resolve())
    session.speaker = FakeSpeaker()  # type: ignore[assignment]
    return session


def _stop(message: str) -> HookContext:
    return HookContext(event=HookEvent.STOP, event_data={}, last_assistant_message=message)


def _model(monkeypatch, spoken: str = REPAIRED, emotion: str = ""):
    """A repair that answers, and a count of how often it was asked."""
    asked: list[str] = []

    async def _repair(text, model=None, timeout=0):
        asked.append(text)
        return RepairedSpeech(spoken=spoken, emotion=emotion)

    monkeypatch.setattr(feature, "repair_for_speech", _repair)
    return asked


@pytest.mark.asyncio
async def test_a_reply_that_missed_its_block_is_heard_as_a_line(monkeypatch):
    """The listener gets the answer, and the table is never read out."""
    asked = _model(monkeypatch)
    session = _session()

    await session.handle_stop(_stop(TABLE))

    assert session.speaker.said == [REPAIRED]
    assert "cost" not in " ".join(session.speaker.said)
    assert asked == [TABLE]


@pytest.mark.asyncio
async def test_a_reply_that_marked_its_block_asks_no_model(monkeypatch):
    """A turn that behaves must cost nothing extra: no call, and the block is
    what is spoken."""
    asked = _model(monkeypatch)
    session = _session()

    await session.handle_stop(_stop(f"<spoken>{REPAIRED}</spoken>\n\n{TABLE}"))

    assert asked == []
    assert session.speaker.said == [REPAIRED]


@pytest.mark.asyncio
async def test_a_short_answer_asks_no_model(monkeypatch):
    """A short answer needs no block, so there is nothing to repair."""
    asked = _model(monkeypatch)
    session = _session()

    await session.handle_stop(_stop("Yes."))

    assert asked == []
    assert session.speaker.said == ["Yes."]


@pytest.mark.asyncio
async def test_the_repair_is_said_in_the_voice_it_names(monkeypatch):
    _model(monkeypatch, spoken=REPAIRED, emotion="happy")
    session = _session(emotion_voices={"happy": "cheerful"})

    await session.handle_stop(_stop(TABLE))

    assert session.speaker.voices == ["cheerful"]


@pytest.mark.asyncio
async def test_a_failing_repair_reads_the_reply_whole(monkeypatch, caplog):
    """The fallback is what would have happened without any of this — never
    silence."""

    async def _broken(text, model=None, timeout=0):
        raise SpeechRepairError("the model was late")

    monkeypatch.setattr(feature, "repair_for_speech", _broken)
    session = _session()

    await session.handle_stop(_stop(LONG))

    assert session.speaker.said == [LONG.strip()]
    assert any("not repaired" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_the_repair_can_be_switched_off(monkeypatch):
    asked = _model(monkeypatch)
    session = _session(repair_enabled=False)

    await session.handle_stop(_stop(LONG))

    assert asked == []
    assert session.speaker.said == [LONG.strip()]


@pytest.mark.asyncio
async def test_repairing_does_not_depend_on_the_notice_switch(monkeypatch):
    """Two switches, two jobs: the notice is a line in the next request, the
    repair is what this turn is heard as. Turning the notice off must not take
    the ear's fix with it."""
    asked = _model(monkeypatch)
    session = _session(block_notice_enabled=False)

    await session.handle_stop(_stop(TABLE))

    assert asked == [TABLE]
    assert session.speaker.said == [REPAIRED]


@pytest.mark.asyncio
async def test_a_late_repair_is_dropped_when_a_newer_reply_arrives(monkeypatch):
    """The turn moved on while the model was thinking, so this line is about a
    reply the listener has already replaced."""
    session = _session()

    async def _slow(text, model=None, timeout=0):
        # the next turn lands before the model answers this one
        await session.handle_stop(_stop("<spoken>Newer.</spoken>"))
        return RepairedSpeech(spoken=REPAIRED)

    monkeypatch.setattr(feature, "repair_for_speech", _slow)

    await session.handle_stop(_stop(TABLE))

    assert session.speaker.said == ["Newer."]


@pytest.mark.asyncio
async def test_a_stale_repair_that_fails_does_not_speak_the_old_reply(monkeypatch):
    """The fallback belongs to *this* reply. If the turn moved on while the model
    was asked, a failure must not resurrect words already replaced."""
    session = _session()

    async def _slow_and_broken(text, model=None, timeout=0):
        # the next turn lands before the model gives up
        await session.handle_stop(_stop("<spoken>Newer.</spoken>"))
        raise SpeechRepairError("the model was late")

    monkeypatch.setattr(feature, "repair_for_speech", _slow_and_broken)

    await session.handle_stop(_stop(TABLE))

    assert session.speaker.said == ["Newer."]


@pytest.mark.asyncio
async def test_a_repair_with_nothing_a_voice_can_say_reads_the_reply_whole(
    monkeypatch, caplog
):
    """A line of nothing but a table cleans away to nothing. Passing it on would
    hand the ear silence, which is the one thing the fallback must never do."""
    _model(monkeypatch, spoken="| item | cost |\n| --- | --- |\n| a | 1 |")
    session = _session()

    await session.handle_stop(_stop(LONG))

    assert session.speaker.said == [LONG.strip()]
    assert any("not repaired" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_a_subagents_missed_block_is_not_repaired(monkeypatch):
    """A delegated run's words were never meant for the ear."""
    asked = _model(monkeypatch)
    session = _session()

    await session.handle_stop(
        HookContext(
            event=HookEvent.STOP,
            event_data={"nested_run": True},
            last_assistant_message=TABLE,
        )
    )

    assert asked == []
    assert session.speaker.said == []
