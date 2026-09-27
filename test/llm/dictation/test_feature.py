import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from zrb.config.config import CFG
from zrb.contextvars import current_chat_session_id
from zrb.llm.dictation import AnyDictationBackend, DictationConfig, enable_dictation
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import Utterance
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
    """Make the microphone hear *said*: (text, started_at, ended_at) each."""
    heard = []

    async def listen(config, should_listen, keep_partial=False):
        heard.append(keep_partial)
        for text, started_at, ended_at in said:
            if not should_listen():
                return
            yield Utterance(text.encode(), started_at, ended_at)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    return heard


async def _replies(session: DictationSession, count: int) -> list[str]:
    stream = session.listen_hands_free()
    replies = [await anext(stream) for _ in range(count)]
    await stream.aclose()
    return [reply.text for reply in replies]


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

    async def listen(config, should_listen, keep_partial=False):
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


def test_hands_free_command_switches_the_mode(monkeypatch):
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))
    session = _session(hands_free_commands=["/handsfree"])
    (command,) = [c for c in session.create_commands() if c.command == "/handsfree"]

    assert command.handle({}, None) == "🎤 Hands-free on"
    assert session.is_hands_free
    assert command.handle({}, None) == "🎤 Hands-free off"
    assert command.can_run_while_thinking


def test_mode_sets_where_a_session_starts():
    assert _session(mode="hands_free").is_hands_free
    assert not _session(mode="ptt").is_hands_free


@pytest.mark.asyncio
async def test_hands_free_turns_each_utterance_into_a_reply(monkeypatch):
    _fake_listen(monkeypatch, ("open the file", 0, 1), ("Yes.", 2, 3))
    session = _session(mode="hands_free")

    assert await _replies(session, 2) == ["open the file", "yes"]


@pytest.mark.asyncio
async def test_hands_free_with_wake_words_keeps_only_what_follows_one(monkeypatch):
    _fake_listen(
        monkeypatch,
        ("what a nice day", 0, 1),
        ("Hey Jarvis, open the file", 2, 3),
    )
    session = _session(mode="hands_free", wake_words=["hey jarvis"])

    assert await _replies(session, 1) == ["open the file"]


@pytest.mark.asyncio
async def test_a_wake_word_alone_accepts_the_next_utterance_in_time(monkeypatch):
    _fake_listen(
        monkeypatch,
        ("Hey Jarvis.", 0, 1),
        ("open the file", 2, 3),
        ("Hey Jarvis", 10, 11),
        ("too late", 30, 31),
        ("hey jarvis run it", 32, 33),
    )
    session = _session(mode="hands_free", wake_words=["hey jarvis"], wake_window=8)

    assert await _replies(session, 2) == ["open the file", "run it"]


@pytest.mark.asyncio
async def test_a_failed_transcription_is_skipped(monkeypatch):
    _fake_listen(monkeypatch, ("bad", 0, 1), ("good", 2, 3))
    session = DictationSession(
        DictationConfig(mode="hands_free", backend=FakeBackend(b"bad")).resolve()
    )

    assert await _replies(session, 1) == ["good"]


@pytest.mark.asyncio
async def test_a_broken_microphone_switches_hands_free_off(monkeypatch):
    async def listen(config, should_listen, keep_partial=False):
        raise OSError("no input device")
        yield  # pragma: no cover

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    session = _session(mode="hands_free")
    stream = session.listen_hands_free()

    waiting = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0.05)

    assert not session.is_hands_free
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting


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

    assert reply == TriggerReply("hello")


def test_hands_free_without_the_audio_extra_says_how_to_install_it(monkeypatch):
    def missing():
        raise RuntimeError("Dictation needs the zrb[voice] extra")

    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", missing)
    session = _session(hands_free_commands=["/handsfree"])

    assert "zrb[voice]" in session.toggle_hands_free({}, None)
    assert not session.is_hands_free


@pytest.mark.asyncio
async def test_any_of_several_wake_words_counts(monkeypatch):
    """The spellings a transcriber produces for one spoken "Hi" all count."""
    _fake_listen(
        monkeypatch,
        ("Hai, open the file", 0, 1),
        ("嗨，run the tests", 2, 3),
        ("hello there", 4, 5),
        ("Hey. Commit it", 6, 7),
    )
    monkeypatch.setattr(CFG, "LLM_DICTATION_WAKE_WORDS", ["hi", "hai", "hey", "嗨"])
    session = _session(mode="hands_free")

    assert await _replies(session, 3) == ["open the file", "run the tests", "Commit it"]


@pytest.mark.asyncio
async def test_an_utterance_being_transcribed_at_switch_off_is_dropped(monkeypatch):
    """Transcription takes seconds, so the user can say stop while one is
    running. That utterance belongs to them, so it must not be submitted —
    and the microphone it was read from has to close with it."""
    transcribing = asyncio.Event()
    release = asyncio.Event()
    closed = asyncio.Event()

    class SlowBackend(FakeBackend):
        async def transcribe(self, audio: bytes) -> str:
            transcribing.set()
            await release.wait()
            return audio.decode()

    async def listen(config, should_listen, keep_partial=False):
        try:
            yield Utterance(b"run the tests", 0.0, 1.0)
            await asyncio.Event().wait()
            yield  # pragma: no cover
        finally:
            closed.set()

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    session = DictationSession(DictationConfig(mode="hands_free").resolve())
    session.backend = SlowBackend()
    stream = session.listen_hands_free()

    waiting = asyncio.ensure_future(anext(stream))
    await asyncio.wait_for(transcribing.wait(), 5)
    session.toggle_hands_free({}, None)

    await asyncio.wait_for(closed.wait(), 5)
    # The listener keeps waiting for hands-free to come back on, but the
    # utterance the user retracted never becomes a reply.
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(waiting, 0.5)
    release.set()
    await stream.aclose()


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
