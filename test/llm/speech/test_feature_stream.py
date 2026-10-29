"""Speech while a reply streams, and the live context telling the model it
is heard."""

from types import SimpleNamespace

import pytest

from zrb.llm.ambient_state import current_reply_emotion
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.speech import SpeechConfig, enable_speech
from zrb.llm.speech.feature import SpeechSession
from zrb.llm.util.feature_config import close_feature_sessions


class FakeSpeaker:
    def __init__(self):
        self.said: list[str] = []
        self.voices: list[str] = []
        self.stale_checks = []
        self.cleared = 0
        self.interrupted = 0
        self.is_enabled = True

    def say(self, text, is_stale=None, voice=""):
        self.said.append(text)
        self.voices.append(voice)
        if is_stale is not None:
            self.stale_checks.append(is_stale)

    def clear(self):
        self.cleared += 1

    def interrupt(self):
        self.interrupted += 1

    def close(self):
        pass


class PersistentHookTask:
    def __init__(self):
        self.hook_manager = HookManager()
        self.prompt_manager = PromptManager(include_sections=[])
        self.stream_observers = []

    def append_hook_factory(self, factory):
        factory(self.hook_manager)

    def append_stream_observer(self, observer):
        self.stream_observers.append(observer)


def _session(**config) -> SpeechSession:
    config.setdefault("enabled", True)
    session = SpeechSession(SpeechConfig(**config).resolve())
    session.speaker = FakeSpeaker()
    return session


def _stop(message: str) -> HookContext:
    return HookContext(
        event=HookEvent.STOP, event_data={}, last_assistant_message=message
    )


def _text_start(content: str):
    return SimpleNamespace(
        event_kind="part_start", part=SimpleNamespace(part_kind="text", content=content)
    )


def _text_delta(content: str):
    return SimpleNamespace(
        event_kind="part_delta",
        delta=SimpleNamespace(part_delta_kind="text", content_delta=content),
    )


def _tool_call_start():
    return SimpleNamespace(
        event_kind="part_start", part=SimpleNamespace(part_kind="tool-call")
    )


@pytest.mark.asyncio
async def test_a_streamed_reply_is_spoken_a_sentence_at_a_time():
    session = _session(stream=True)
    first = "I will check the test suite first. "
    rest = "Then I will fix the failing case. "

    session.handle_stream_event(_text_start("<spoken>"))
    for i in range(0, len(first), 4):
        session.handle_stream_event(_text_delta(first[i : i + 4]))

    assert session.speaker.said == ["I will check the test suite first."]

    for i in range(0, len(rest), 4):
        session.handle_stream_event(_text_delta(rest[i : i + 4]))

    assert session.speaker.said == [
        "I will check the test suite first.",
        "Then I will fix the failing case.",
    ]


@pytest.mark.asyncio
async def test_a_reply_is_read_in_the_voice_of_the_emotion_it_opens_with():
    session = _session(stream=True, emotion_voices={"sad": "sad.wav"})

    # The emotion feature sets it as it takes the emoji out of the reply.
    token = current_reply_emotion.set("sad")
    try:
        session.handle_stream_event(
            _text_start("<spoken>The build failed. Again.</spoken>")
        )
        session.handle_stream_event(_tool_call_start())
    finally:
        current_reply_emotion.reset(token)
    session.handle_stream_event(_text_start("<spoken>I will look.</spoken>"))
    session.handle_stream_event(_tool_call_start())

    assert session.speaker.said == ["The build failed. Again.", "I will look."]
    assert session.speaker.voices == ["sad.wav", ""]


@pytest.mark.asyncio
async def test_a_reply_spoken_at_stop_reads_its_emotions_voice():
    session = _session(stream=False, emotion_voices={"happy": "happy.wav"})

    token = current_reply_emotion.set("happy")
    try:
        await session.handle_stop(_stop("All green."))
    finally:
        current_reply_emotion.reset(token)

    assert session.speaker.said == ["All green."]
    assert session.speaker.voices == ["happy.wav"]


def test_only_the_spoken_block_is_read_aloud_while_it_streams():
    session = _session(stream=True)

    session.handle_stream_event(_text_start("<spoken>"))
    session.handle_stream_event(_text_delta("The build failed. Again."))
    session.handle_stream_event(_text_delta("</spoken> Here is the log."))
    session.handle_stream_event(_tool_call_start())

    assert session.speaker.said == ["The build failed. Again."]


@pytest.mark.asyncio
async def test_a_reply_spoken_at_stop_reads_its_block_and_not_the_detail():
    session = _session(stream=False)

    await session.handle_stop(
        _stop("<spoken>😊 All green.</spoken>\n`main.py`: three tests added.")
    )

    assert session.speaker.said == ["All green."]


@pytest.mark.asyncio
async def test_a_reply_with_no_block_is_read_whole_as_before():
    """What makes the block safe to forget: a model that never writes one is
    heard exactly as it was before the block existed."""
    session = _session(stream=False)
    reply = "The build failed. I will look at the log."

    await session.handle_stop(_stop(reply))

    assert session.speaker.said == [reply]


def test_prose_before_a_block_is_never_said():
    """Nothing outside a block reaches the ear, before it or after it: the
    stream says only what a block marks."""
    session = _session(stream=True)

    session.handle_stream_event(_text_start(""))
    session.handle_stream_event(_text_delta("Let me check. "))
    assert session.speaker.said == []

    session.handle_stream_event(_text_delta("<spoken>Done.</spoken>"))
    session.handle_stream_event(_tool_call_start())

    assert session.speaker.said == ["Done."]


def test_a_block_does_not_cost_a_reply_its_emotions_voice():
    """The emoji sits inside the block, as its first character; the emotion
    feature still reads it, and the voice still follows it."""
    session = _session(stream=True, emotion_voices={"sad": "sad.wav"})

    token = current_reply_emotion.set("sad")
    try:
        session.handle_stream_event(_text_start("<spoken>"))
        session.handle_stream_event(_text_delta("The build failed. Again."))
        session.handle_stream_event(_text_delta("</spoken> The log is long."))
        session.handle_stream_event(_tool_call_start())
    finally:
        current_reply_emotion.reset(token)

    assert session.speaker.said == ["The build failed. Again."]
    assert session.speaker.voices == ["sad.wav"]


def test_a_streamed_chunk_stops_at_the_length_the_voice_can_take():
    """A local engine drops words past its own token window, so how much prose
    one chunk may hold is the setting's, not the chunker's default."""
    session = _session(stream=True, chunk_max_chars=40)
    reply = "one two three four, five six seven eight nine"

    session.handle_stream_event(_text_start("<spoken>"))
    session.handle_stream_event(_text_delta(reply))
    session.handle_stream_event(_tool_call_start())

    assert session.speaker.said[0] == "one two three four,"


def test_a_block_before_a_tool_call_is_spoken_when_the_call_starts():
    session = _session(stream=True)

    session.handle_stream_event(_text_start("<spoken>Let me look.</spoken>"))
    session.handle_stream_event(_tool_call_start())

    assert session.speaker.said == ["Let me look."]


@pytest.mark.asyncio
async def test_a_streamed_turn_is_spoken_whole_however_long_it_is():
    """Nothing caps what one turn says: the whole reply is read, so nothing is
    left unsaid and there is no note about what was."""
    session = _session(stream=True)
    sentence = "This sentence is about forty characters. "

    session.handle_stream_event(_text_start("<spoken>"))
    for _ in range(4):
        session.handle_stream_event(_text_delta(sentence))
    session.handle_stream_event(_tool_call_start())

    assert session.speaker.said == [sentence.strip()] * 4


@pytest.mark.asyncio
async def test_a_turn_that_streamed_nothing_is_spoken_at_stop():
    session = _session(stream=True)

    await session.handle_stop(_stop("Done."))

    assert session.speaker.said == ["Done."]


@pytest.mark.asyncio
async def test_stream_events_are_ignored_unless_stream_is_on():
    session = _session(stream=False)

    session.handle_stream_event(_text_delta("A whole sentence is here now. "))

    assert session.speaker.said == []


@pytest.mark.asyncio
async def test_a_turn_cancelled_with_escape_is_not_finished_aloud():
    session = _session(stream=True)
    session.handle_stream_event(_text_delta("half a sentence"))

    await session.handle_stop(
        HookContext(event=HookEvent.STOP, event_data={"reason": "escape"})
    )

    assert session.speaker.said == []
    # The sentence playing is stopped too, not only the queue.
    assert session.speaker.interrupted == 1


@pytest.mark.asyncio
async def test_a_progress_only_turn_cancelled_with_escape_stops_what_is_playing():
    """A cancel stops the speaker whatever it is saying. A `progress`-only
    session speaks no reply, but a progress line may be playing when the turn is
    cancelled (review on #579)."""
    session = _session(events=["progress"])

    await session.handle_stop(
        HookContext(event=HookEvent.STOP, event_data={"reason": "escape"})
    )

    assert session.speaker.interrupted == 1


def test_enable_speech_registers_a_stream_observer():
    task = PersistentHookTask()
    enable_speech(task, SpeechConfig(enabled=True, stream=True))
    try:
        assert len(task.stream_observers) == 1
    finally:
        close_feature_sessions("")


def test_the_live_context_says_the_reply_is_heard_only_while_it_is():
    session = _session(events=["reply"])
    assert "read aloud" in session.create_live_context()

    session.speaker.is_enabled = False
    assert session.create_live_context() == ""

    assert _session(events=["approval"]).create_live_context() == ""


def test_enable_speech_adds_a_live_context_to_the_tasks_prompt_manager():
    task = PersistentHookTask()
    enable_speech(task, SpeechConfig(enabled=True, events=["reply"]))
    enable_speech(task, SpeechConfig(enabled=True, events=["reply"]))
    try:
        providers = task.prompt_manager.get_live_contexts()
        assert [name for name, _ in providers] == ["speech"]
        assert "read aloud" in providers[0][1](None)
    finally:
        close_feature_sessions("")


def _tool_call(tool, args=None):
    return SimpleNamespace(
        event_kind="function_tool_call",
        part=SimpleNamespace(tool_name=tool, tool_call_id="c1", args=args),
    )


def test_a_tool_call_after_a_silence_is_announced_with_progress(monkeypatch):
    monkeypatch.setattr("zrb.llm.speech.feature.is_speaking", lambda lock: False)
    session = _session(events=["progress"], progress_interval=5)

    session.handle_stream_event(_tool_call("Shell"))

    assert session.speaker.said == ["Running a command."]


def test_the_call_s_own_purpose_is_what_is_announced(monkeypatch):
    """The narration reaches the speaker as the model wrote the purpose, not
    as the Shell phrase it stands in for."""
    monkeypatch.setattr("zrb.llm.speech.feature.is_speaking", lambda lock: False)
    session = _session(events=["progress"], progress_interval=5)

    session.handle_stream_event(
        _tool_call("Shell", args={"purpose": "Getting the biggest file"})
    )

    assert session.speaker.said == ["Getting the biggest file"]


@pytest.mark.asyncio
async def test_a_progress_announcement_is_dropped_when_turn_stops_without_result(
    monkeypatch,
):
    monkeypatch.setattr("zrb.llm.speech.feature.is_speaking", lambda lock: False)
    session = _session(stream=True, events=["reply", "progress"], progress_interval=5)

    session.handle_stream_event(_tool_call("Shell"))
    [is_stale] = session.speaker.stale_checks

    await session.handle_stop(
        HookContext(event=HookEvent.STOP, event_data={}, last_assistant_message=None)
    )

    assert is_stale() is True


def test_a_tool_call_right_after_its_spoken_intro_is_not_announced(monkeypatch):
    monkeypatch.setattr("zrb.llm.speech.feature.is_speaking", lambda lock: False)
    session = _session(stream=True, events=["reply", "progress"], progress_interval=5)

    session.handle_stream_event(_text_start("<spoken>Let me run the tests.</spoken>"))
    session.handle_stream_event(_tool_call_start())
    session.handle_stream_event(_tool_call("Shell"))

    assert session.speaker.said == ["Let me run the tests."]


def test_nothing_is_announced_while_speech_is_playing(monkeypatch):
    monkeypatch.setattr("zrb.llm.speech.feature.is_speaking", lambda lock: True)
    session = _session(events=["progress"], progress_interval=5)

    session.handle_stream_event(_tool_call("Shell"))

    assert session.speaker.said == []


def test_nothing_streams_or_is_announced_while_speech_is_off():
    session = _session(stream=True, events=["reply", "progress"])
    session.speaker.is_enabled = False

    session.handle_stream_event(_text_delta("A whole sentence is right here. "))
    session.handle_stream_event(_tool_call("Shell"))

    assert session.speaker.said == []


@pytest.mark.asyncio
async def test_interrupt_speech_silences_this_chat_session_only():
    from zrb.contextvars import current_chat_session_id
    from zrb.llm.speech import interrupt_speech

    sessions = {}
    for name in ("mine", "other"):
        token = current_chat_session_id.set(name)
        try:
            sessions[name] = _session(stream=True)
            sessions[name].speaker = FakeSpeaker()
        finally:
            current_chat_session_id.reset(token)
    try:
        interrupt_speech("mine")

        assert sessions["mine"].speaker.interrupted == 1
        assert sessions["other"].speaker.interrupted == 0
        # Talked over mid-reply: the rest of the reply is not spoken at Stop.
        await sessions["mine"].handle_stop(_stop("The whole reply."))
        assert sessions["mine"].speaker.said == []
    finally:
        for session in sessions.values():
            session.close()


def test_a_closed_session_is_no_longer_interrupted():
    from zrb.llm.speech import interrupt_speech

    session = _session()
    session.speaker = FakeSpeaker()
    session.close()

    interrupt_speech("")

    assert session.speaker.interrupted == 0


def test_pause_and_resume_speech_reach_this_chat_sessions_speaker():
    from zrb.llm.speech import pause_speech, resume_speech

    class ControlledSpeaker(FakeSpeaker):
        def __init__(self):
            super().__init__()
            self.events: list[str] = []

        def pause(self):
            self.events.append("pause")

        def resume(self):
            self.events.append("resume")

    session = _session()
    session.speaker = ControlledSpeaker()
    try:
        pause_speech()
        resume_speech()
        pause_speech("another chat")
        assert session.speaker.events == ["pause", "resume"]
    finally:
        session.close()


def test_a_failing_speaker_does_not_stop_speech_control(caplog):
    from zrb.llm.speech import pause_speech

    class BrokenSpeaker(FakeSpeaker):
        def pause(self):
            raise RuntimeError("device gone")

    session = _session()
    session.speaker = BrokenSpeaker()
    try:
        pause_speech()
        assert "device gone" in caplog.text
    finally:
        session.close()
