import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from zrb.config.config import CFG
from zrb.contextvars import current_chat_session_id
from zrb.llm.dictation import AnyDictationBackend, DictationConfig, enable_dictation
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import MicState, Utterance
from zrb.llm.ui.trigger import TriggerReply


class FakeBackend(AnyDictationBackend):
    """Transcribes each clip to the text it was built from."""

    def __init__(self, fail_on: bytes = b""):
        self.fail_on = fail_on
        self.prepared = 0

    async def prepare(self, report):
        self.prepared += 1
        report("getting ready")

    async def transcribe(self, audio: bytes) -> str:
        if self.fail_on and audio == self.fail_on:
            raise RuntimeError("garbled")
        return audio.decode()


class FakeUI:
    def __init__(self):
        self.background_tasks: set = set()
        self.outputs: list[str] = []
        self.inserted: list[str] = []
        self.badges: list[tuple[str, str | None]] = []

    def set_status_badge(self, key, text):
        self.badges.append((key, text))

    def append_to_output(self, text):
        self.outputs.append(text)

    def insert_input_text(self, text):
        self.inserted.append(text)


@contextmanager
def _as_session(name: str):
    """Run the block as chat session *name*, the way the web runner does."""
    token = current_chat_session_id.set(name)
    try:
        yield
    finally:
        current_chat_session_id.reset(token)


def _session(**config) -> DictationSession:
    return DictationSession(DictationConfig(backend=FakeBackend(), **config).resolve())


def _fake_listen(monkeypatch, *said: tuple[str, float, float]):
    """Make the microphone hear *said*: (text, started_at, ended_at) each. Also
    make the audio extra look installed, since a machine without PortAudio is
    not what these tests are about."""
    heard = []

    async def listen(
        config,
        should_listen,
        keep_partial=False,
        on_state=None,
        on_barge_in=None,
        **kwargs,
    ):
        heard.append(keep_partial)
        for text, started_at, ended_at in said:
            if not should_listen():
                return
            if on_state is not None:
                on_state(MicState.HEARING)
                on_state(MicState.LISTENING)
            yield Utterance(text.encode(), started_at, ended_at)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))
    return heard


async def _trigger_replies(session: DictationSession, count: int) -> list[TriggerReply]:
    stream = session.listen_hands_free()
    replies = [await anext(stream) for _ in range(count)]
    await stream.aclose()
    return replies


@pytest.mark.asyncio
async def test_push_to_talk_puts_the_transcript_in_the_input_box(monkeypatch):
    heard = _fake_listen(monkeypatch, ("run the tests", 0.0, 1.0))
    session = _session(commands=["/voice"])
    ui = FakeUI()

    session.create_commands()[0].handle({}, ui)
    assert session.is_recording
    await asyncio.gather(*ui.background_tasks)
    await asyncio.sleep(0)

    assert ui.inserted == ["run the tests"]
    assert heard == [True]  # speech cut off by the stop is kept
    assert not session.is_recording
    assert any("getting ready" in output for output in ui.outputs)
    assert any("Transcribed" in output for output in ui.outputs)
    assert [text for _, text in ui.badges] == [
        "🔴 recording… (/voice or a pause to stop)",
        "📝 transcribing…",
        None,
    ]


@pytest.mark.asyncio
async def test_push_to_talk_says_so_when_nothing_was_heard(monkeypatch):
    _fake_listen(monkeypatch)
    session = _session(commands=["/voice"])
    ui = FakeUI()

    session.create_commands()[0].handle({}, ui)
    await asyncio.gather(*ui.background_tasks)
    await asyncio.sleep(0)

    assert ui.inserted == []
    assert any("Heard nothing" in output for output in ui.outputs)


@pytest.mark.asyncio
async def test_the_command_again_stops_the_recording(monkeypatch):
    stopped = asyncio.Event()

    async def listen(
        config,
        should_listen,
        keep_partial=False,
        on_state=None,
        on_barge_in=None,
        **kwargs,
    ):
        while should_listen():
            await asyncio.sleep(0)
        stopped.set()
        yield Utterance(b"half a sentence", 0.0, 1.0)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    session = _session(commands=["/voice"])
    ui = FakeUI()
    voice = session.create_commands()[0]

    voice.handle({}, ui)
    await asyncio.sleep(0)
    assert voice.handle({}, ui) == "🎤 Stopping..."
    await asyncio.gather(*ui.background_tasks)

    assert stopped.is_set()
    assert ui.inserted == ["half a sentence"]


def test_push_to_talk_needs_a_ui_and_hands_free_off():
    session = _session(commands=["/voice"])
    assert "interactive" in session.toggle_recording({}, None)

    session.is_hands_free = True
    assert "Hands-free is on" in session.toggle_recording({}, FakeUI())
    assert not session.is_recording


@pytest.mark.asyncio
async def test_enable_dictation_reads_cfg_when_a_session_starts(monkeypatch):
    chat = MagicMock()
    enable_dictation(chat, DictationConfig(backend=FakeBackend()))
    (create_commands,) = chat.append_custom_command.call_args.args
    (hands_free,) = chat.append_trigger.call_args.args

    monkeypatch.setattr(CFG, "LLM_DICTATION_COMMANDS", ["/talk"])
    monkeypatch.setattr(CFG, "LLM_DICTATION_HANDS_FREE_COMMANDS", ["/listen"])
    assert [c.command for c in create_commands()] == ["/talk", "/listen"]


@pytest.mark.asyncio
async def test_enabled_trigger_relays_the_session_replies(monkeypatch):
    _fake_listen(monkeypatch, ("hello", 0, 1))
    chat = MagicMock()
    enable_dictation(chat, DictationConfig(mode="hands_free", backend=FakeBackend()))
    (hands_free,) = chat.append_trigger.call_args.args

    stream = hands_free()
    reply = await anext(stream)
    await stream.aclose()

    assert reply == TriggerReply("hello", approval="hello", started_at=0)


@pytest.mark.asyncio
async def test_two_sessions_hands_free_state_is_their_own(monkeypatch):
    _fake_listen(monkeypatch, ("run the tests", 0.0, 1.0))
    chat = MagicMock()
    enable_dictation(
        chat,
        DictationConfig(
            commands=[],
            hands_free_commands=["/handsfree"],
            backend=FakeBackend(),
        ),
    )
    (create_commands,) = chat.append_custom_command.call_args.args
    (hands_free,) = chat.append_trigger.call_args.args

    with _as_session("first"):
        (first,) = create_commands()
        assert first.handle({}, None) == "🎤 Hands-free on"
        first_stream = hands_free()
        assert (await asyncio.wait_for(anext(first_stream), 5)).text == "run the tests"
        await first_stream.aclose()

    with _as_session("second"):
        second_stream = hands_free()
        waiting = asyncio.ensure_future(anext(second_stream))
        await asyncio.sleep(0.1)
        # The second session's own hands-free is off, whatever the first did.
        assert not waiting.done()
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting


@pytest.mark.asyncio
async def test_enabling_dictation_again_uses_the_new_config(monkeypatch):
    """Same as speech: the second `enable_*` call is the one that has to reach
    the sessions started after it."""
    _fake_listen(monkeypatch, ("run the tests", 0.0, 1.0))
    chat = MagicMock()

    enable_dictation(
        chat,
        DictationConfig(
            commands=["/first"], hands_free_commands=[], backend=FakeBackend()
        ),
    )
    (first_commands,) = chat.append_custom_command.call_args.args
    assert [c.command for c in first_commands()] == ["/first"]

    enable_dictation(
        chat,
        DictationConfig(
            commands=["/second"], hands_free_commands=[], backend=FakeBackend()
        ),
    )
    (second_commands,) = chat.append_custom_command.call_args.args
    assert [c.command for c in second_commands()] == ["/second"]


def test_an_unknown_backend_does_not_break_a_session_that_never_uses_it(monkeypatch):
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))
    session = DictationSession(
        DictationConfig(
            backend="whisper", commands=["/voice"], hands_free_commands=["/handsfree"]
        ).resolve()
    )
    voice, hands_free = session.create_commands()

    assert "unknown dictation backend" in voice.handle({}, FakeUI())
    assert not session.is_recording
    assert "unknown dictation backend" in hands_free.handle({}, None)
    assert not session.is_hands_free


@pytest.mark.asyncio
async def test_a_recording_cancelled_before_it_starts_can_be_started_again(
    monkeypatch,
):
    _fake_listen(monkeypatch)
    session = _session(commands=["/voice"])
    ui = FakeUI()
    voice = session.create_commands()[0]

    voice.handle({}, ui)
    for task in ui.background_tasks:
        task.cancel()
    await asyncio.gather(*ui.background_tasks, return_exceptions=True)
    await asyncio.sleep(0)

    assert not session.is_recording
    assert voice.handle({}, ui) == ""
    await asyncio.gather(*ui.background_tasks)
