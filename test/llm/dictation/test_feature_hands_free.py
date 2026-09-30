"""Hands-free dictation: wake words, switching, and what reaches the chat."""

import asyncio

import pytest

from zrb.config.config import CFG
from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.feature import BADGE_KEY, DictationSession
from zrb.llm.dictation.listen import MicState, Utterance
from zrb.llm.ui.trigger import TriggerReply
from zrb.llm.util.feature_config import reset_session_ui, set_session_ui


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


def _session(**config) -> DictationSession:
    return DictationSession(DictationConfig(backend=FakeBackend(), **config).resolve())


def _fake_listen(monkeypatch, *said: tuple[str, float, float]):
    """Make the microphone hear *said*: (text, started_at, ended_at) each. Also
    make the audio extra look installed, since a machine without PortAudio is
    not what these tests are about."""
    heard = []

    async def listen(
        config, should_listen, keep_partial=False, on_state=None, on_barge_in=None
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


async def _replies(session: DictationSession, count: int) -> list[str]:
    return [reply.text for reply in await _trigger_replies(session, count)]


async def _trigger_replies(session: DictationSession, count: int) -> list[TriggerReply]:
    stream = session.listen_hands_free()
    replies = [await anext(stream) for _ in range(count)]
    await stream.aclose()
    return replies


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

    assert await _trigger_replies(session, 2) == [
        TriggerReply("open the file", approval="open the file", started_at=0),
        TriggerReply("Yes.", approval="yes", started_at=2),
    ]


@pytest.mark.asyncio
async def test_a_command_opening_with_an_approve_word_is_sent_as_said(monkeypatch):
    _fake_listen(monkeypatch, ("ok run the tests", 0, 1), ("Okay, no, stop.", 2, 3))
    session = _session(mode="hands_free")

    assert await _trigger_replies(session, 2) == [
        TriggerReply("ok run the tests", approval="ok run the tests", started_at=0),
        TriggerReply("Okay, no, stop.", approval="Okay, no, stop.", started_at=2),
    ]


@pytest.mark.asyncio
async def test_an_empty_transcript_does_not_extend_the_wake_window(monkeypatch):
    _fake_listen(
        monkeypatch,
        ("Hey Jarvis", 0, 1),
        ("", 5, 6),
        ("background chatter", 12, 13),
        ("hey jarvis run it", 20, 21),
    )
    session = _session(mode="hands_free", wake_words=["hey jarvis"], wake_window=8)

    assert await _replies(session, 1) == ["run it"]


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
    async def listen(
        config, should_listen, keep_partial=False, on_state=None, on_barge_in=None
    ):
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

    async def listen(
        config, should_listen, keep_partial=False, on_state=None, on_barge_in=None
    ):
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
async def test_hands_free_prepares_the_backend_and_reports_to_the_ui(monkeypatch):
    _fake_listen(monkeypatch, ("run the tests", 0, 1))
    backend = FakeBackend()
    session = DictationSession(
        DictationConfig(hands_free_commands=["/handsfree"], backend=backend).resolve()
    )
    ui = FakeUI()

    session.toggle_hands_free({}, ui)
    await _replies(session, 1)

    assert backend.prepared == 1
    assert any("getting ready" in output for output in ui.outputs)


@pytest.mark.asyncio
async def test_a_broken_microphone_is_reported_to_the_ui(monkeypatch):
    async def listen(
        config, should_listen, keep_partial=False, on_state=None, on_barge_in=None
    ):
        raise OSError("no input device")
        yield  # pragma: no cover

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))
    session = _session(hands_free_commands=["/handsfree"])
    ui = FakeUI()
    session.toggle_hands_free({}, ui)
    stream = session.listen_hands_free()

    waiting = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0.05)

    assert any("no input device" in output for output in ui.outputs)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting


@pytest.mark.asyncio
async def test_closing_the_listener_closes_the_microphone_at_once(monkeypatch):
    closed = asyncio.Event()

    async def listen(
        config, should_listen, keep_partial=False, on_state=None, on_barge_in=None
    ):
        try:
            yield Utterance(b"run the tests", 0.0, 1.0)
            await asyncio.Event().wait()
        finally:
            closed.set()

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    session = _session(mode="hands_free")
    stream = session.listen_hands_free()

    await anext(stream)
    await stream.aclose()

    assert closed.is_set()


@pytest.fixture
def session_ui():
    ui = FakeUI()
    set_session_ui(ui)  # type: ignore[arg-type]
    yield ui
    reset_session_ui()


def _badges(ui: FakeUI) -> list[str | None]:
    return [text for key, text in ui.badges if key == BADGE_KEY]


@pytest.mark.asyncio
async def test_hands_free_shows_what_the_mic_is_doing(monkeypatch, session_ui):
    _fake_listen(monkeypatch, ("Yes.", 0, 1))
    session = _session(mode="hands_free")

    await _trigger_replies(session, 1)

    assert _badges(session_ui) == [
        "🎤 listening",
        "🎙️ hearing you…",
        "🎤 listening",
        "✍️ transcribing…",
        '🎤 heard "Yes." · listening',
        None,
    ]


@pytest.mark.asyncio
async def test_hands_free_says_what_an_utterance_came_to(monkeypatch, session_ui):
    _fake_listen(
        monkeypatch,
        ("", 0, 1),
        ("bad", 2, 3),
        ("hello there", 4, 5),
        ("hey zrb", 6, 7),
        ("x" * 60, 8, 9),
    )
    session = DictationSession(
        DictationConfig(
            backend=FakeBackend(fail_on=b"bad"),
            mode="hands_free",
            wake_words=["hey zrb"],
        ).resolve()
    )

    await _trigger_replies(session, 1)

    badges = _badges(session_ui)
    assert "🎤 didn't catch that · listening" in badges
    assert "⚠️ transcription failed · listening" in badges
    assert '🎤 ignored "hello there" (no wake word)' in badges
    assert "🎤 go ahead…" in badges
    assert f'🎤 heard "{"x" * 39}…" · listening' in badges


def test_switching_hands_free_off_clears_the_badge(monkeypatch, session_ui):
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))
    session = _session(hands_free_commands=["/handsfree"])
    (command,) = [c for c in session.create_commands() if c.command == "/handsfree"]

    command.handle({}, None)
    command.handle({}, None)

    assert _badges(session_ui) == [None]
