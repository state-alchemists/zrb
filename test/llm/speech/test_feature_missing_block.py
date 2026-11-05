"""A reply that should have opened a `<spoken>` block and did not.

The rule is prose in the prompt, and nothing else observed the reply, so
leaving the block out used to be silent both ways: the listener heard the
whole reply — table, code, paths — and the writer was never told. These pin
the check and the notice it carries to the next turn.
"""

import pytest

from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.types import HookEvent
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


def _stop(message: str, nested: bool = False) -> HookContext:
    return HookContext(
        event=HookEvent.STOP,
        event_data={"nested_run": True} if nested else {},
        last_assistant_message=message,
    )


@pytest.mark.asyncio
async def test_a_reply_that_wanted_a_block_is_told_about_it_next_turn(caplog):
    """The reply is already heard by the time it can be noticed, so the notice
    is carried to the next turn — which is when the model can still do
    something with it — and the log says so for whoever reads the log."""
    session = _session()

    await session.handle_stop(
        _stop("Where things stand:\n\n| item | cost |\n| --- | --- |\n| a | 1 |")
    )

    assert "no `<spoken>` block" in session.create_live_context()
    assert any("opened no `<spoken>` block" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_a_reply_that_marked_a_block_is_not_told_off():
    """The block is what the rule asks for, so a reply carrying one is
    finished, however much eye-only material sits outside it."""
    session = _session()

    await session.handle_stop(
        _stop("<spoken>Done.</spoken>\n\n| item | cost |\n| --- | --- |\n| a | 1 |")
    )

    assert "no `<spoken>` block" not in session.create_live_context()


@pytest.mark.asyncio
async def test_the_notice_goes_when_the_next_reply_marks_a_block():
    session = _session()
    await session.handle_stop(_stop("A long enough answer. " * 20))
    assert "no `<spoken>` block" in session.create_live_context()

    await session.handle_stop(_stop("<spoken>Done.</spoken>"))

    assert "no `<spoken>` block" not in session.create_live_context()


@pytest.mark.asyncio
async def test_a_short_reply_without_a_block_is_left_alone():
    """A short answer needs no block, so the check must not nag about one."""
    session = _session()

    await session.handle_stop(_stop("Yes."))

    assert "no `<spoken>` block" not in session.create_live_context()


@pytest.mark.asyncio
async def test_a_streamed_reply_that_claimed_the_turn_is_still_checked():
    """A streamed reply is spoken as it arrives and never reaches `say_reply`,
    so a check put there would have missed every one of them."""
    session = _session(stream=True)

    await session.handle_stop(_stop("A long enough answer. " * 20))

    assert "no `<spoken>` block" in session.create_live_context()


@pytest.mark.asyncio
async def test_a_subagents_reply_is_not_the_users_and_is_not_checked():
    """Only the turn the user is in is theirs; a delegated run's words were
    never meant for the ear."""
    session = _session()

    await session.handle_stop(_stop("A long enough answer. " * 20, nested=True))

    assert "no `<spoken>` block" not in session.create_live_context()


@pytest.mark.asyncio
async def test_the_notice_claims_nothing_about_what_was_heard():
    """The reply may be summarized, cut short by a barge-in, or muted between
    being written and being listened to, so the notice states the omission and
    the rule and stops there."""
    session = _session(summarize_above_chars=100)

    await session.handle_stop(_stop("A long enough answer. " * 20))

    context = session.create_live_context()
    assert "no `<spoken>` block" in context
    assert "whole reply" not in context
    assert "summary" not in context


@pytest.mark.asyncio
async def test_a_reply_while_speech_is_off_is_not_noticed():
    """Nobody heard it, so there is nothing to tell the model about it."""
    session = _session()
    session.speaker.is_enabled = False

    await session.handle_stop(_stop("A long enough answer. " * 20))

    session.speaker.is_enabled = True
    assert "no `<spoken>` block" not in session.create_live_context()


@pytest.mark.asyncio
async def test_turning_speech_off_forgets_a_notice_already_standing():
    session = _session()
    await session.handle_stop(_stop("A long enough answer. " * 20))
    assert "no `<spoken>` block" in session.create_live_context()

    session.toggle({}, None)
    session.toggle({}, None)

    assert "no `<spoken>` block" not in session.create_live_context()


@pytest.mark.asyncio
async def test_a_turn_that_says_nothing_replaces_the_note():
    """The notice is about the last reply. A turn with no reply at all leaves
    nothing for it to be about, so an older miss does not carry over."""
    session = _session()
    await session.handle_stop(_stop("A long enough answer. " * 20))
    assert "no `<spoken>` block" in session.create_live_context()

    await session.handle_stop(_stop(""))

    assert "no `<spoken>` block" not in session.create_live_context()


@pytest.mark.asyncio
async def test_the_notice_can_be_switched_off():
    """The notice costs the next request a line, so a session that does not
    want it must not carry it — and must not log a miss either."""
    session = _session(block_notice_enabled=False)

    await session.handle_stop(_stop("A long enough answer. " * 20))

    assert "no `<spoken>` block" not in session.create_live_context()


@pytest.mark.asyncio
async def test_the_notice_is_on_by_default_and_the_knob_reads_cfg(monkeypatch, caplog):
    monkeypatch.setenv("ZRB_LLM_SPEECH_BLOCK_NOTICE_ENABLED", "false")
    session = _session()

    await session.handle_stop(_stop("A long enough answer. " * 20))

    assert "no `<spoken>` block" not in session.create_live_context()
    assert not any(
        "opened no `<spoken>` block" in r.getMessage() for r in caplog.records
    )


@pytest.mark.asyncio
async def test_a_cancelled_turn_replaces_the_note():
    """Esc ends the turn without a finished reply — the same case as the empty
    turn, reached through the hook's `reason`."""
    session = _session()
    await session.handle_stop(_stop("A long enough answer. " * 20))
    assert "no `<spoken>` block" in session.create_live_context()

    await session.handle_stop(
        HookContext(
            event=HookEvent.STOP,
            event_data={"reason": "escape"},
            last_assistant_message="A long enough answer. " * 20,
        )
    )

    assert "no `<spoken>` block" not in session.create_live_context()
