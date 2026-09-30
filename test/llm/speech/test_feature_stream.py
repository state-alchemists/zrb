"""Speech while a reply streams, and the live context telling the model it
is heard."""

from types import SimpleNamespace

import pytest

from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.speech import SpeechConfig, enable_speech
from zrb.llm.speech.feature import SpeechSession
from zrb.llm.util.feature_config import close_feature_sessions

NOTE = "Rest on screen."


class FakeSpeaker:
    def __init__(self):
        self.said: list[str] = []
        self.cleared = 0
        self.is_enabled = True

    def say(self, text, is_stale=None):
        self.said.append(text)

    def clear(self):
        self.cleared += 1

    def interrupt(self):
        pass

    def close(self):
        pass


class PersistentHookTask:
    def __init__(self):
        self.hook_manager = HookManager()

    def append_hook_factory(self, factory):
        factory(self.hook_manager)


def _session(**config) -> SpeechSession:
    config.setdefault("on_screen_note", NOTE)
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
    session = _session(stream=True, max_chars=0)
    reply = "I will check the test suite first. Then I will fix the failing case."

    session.handle_stream_event(_text_start(""))
    for i in range(0, len(reply), 4):
        session.handle_stream_event(_text_delta(reply[i : i + 4]))

    assert session.speaker.said == ["I will check the test suite first."]
    await session.handle_stop(_stop(reply))
    assert session.speaker.said == [
        "I will check the test suite first.",
        "Then I will fix the failing case.",
    ]


@pytest.mark.asyncio
async def test_text_before_a_tool_call_is_spoken_when_the_call_starts():
    session = _session(stream=True)

    session.handle_stream_event(_text_start("Let me look."))
    session.handle_stream_event(_tool_call_start())

    assert session.speaker.said == ["Let me look."]


@pytest.mark.asyncio
async def test_a_streamed_turn_stops_speaking_at_max_chars_with_one_note():
    session = _session(stream=True, max_chars=40)
    sentence = "This sentence is about forty characters. "

    for _ in range(4):
        session.handle_stream_event(_text_delta(sentence))
    await session.handle_stop(_stop(sentence * 4))

    assert session.speaker.said == [sentence.strip(), NOTE]


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
    assert session.speaker.cleared == 1


def test_enable_speech_registers_a_stream_observer_on_a_task_that_takes_one():
    class Observed(PersistentHookTask):
        def __init__(self):
            super().__init__()
            self.stream_observers = []

        def append_stream_observer(self, observer):
            self.stream_observers.append(observer)

    task = Observed()
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
    from zrb.llm.prompt.manager import PromptManager

    class Prompted(PersistentHookTask):
        def __init__(self):
            super().__init__()
            self.prompt_manager = PromptManager(include_sections=[])

    task = Prompted()
    enable_speech(task, SpeechConfig(enabled=True, events=["reply"]))
    enable_speech(task, SpeechConfig(enabled=True, events=["reply"]))
    try:
        providers = task.prompt_manager.get_live_contexts()
        assert [name for name, _ in providers] == ["speech"]
        assert "read aloud" in providers[0][1](None)
    finally:
        close_feature_sessions("")


def _tool_call(tool):
    return SimpleNamespace(
        event_kind="function_tool_call",
        part=SimpleNamespace(tool_name=tool, tool_call_id="c1"),
    )


def test_a_tool_call_after_a_silence_is_announced_with_progress(monkeypatch):
    monkeypatch.setattr("zrb.llm.speech.feature.is_speaking", lambda lock: False)
    session = _session(events=["progress"], progress_interval=5)

    session.handle_stream_event(_tool_call("Shell"))

    assert session.speaker.said == ["Running a command."]


def test_a_tool_call_right_after_its_spoken_intro_is_not_announced(monkeypatch):
    monkeypatch.setattr("zrb.llm.speech.feature.is_speaking", lambda lock: False)
    session = _session(stream=True, events=["reply", "progress"], progress_interval=5)

    session.handle_stream_event(_text_start("Let me run the tests."))
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


class InterruptibleSpeaker(FakeSpeaker):
    def __init__(self):
        super().__init__()
        self.interrupted = 0

    def interrupt(self):
        self.interrupted += 1


@pytest.mark.asyncio
async def test_interrupt_speech_silences_this_chat_session_only():
    from zrb.contextvars import current_chat_session_id
    from zrb.llm.speech import interrupt_speech

    sessions = {}
    for name in ("mine", "other"):
        token = current_chat_session_id.set(name)
        try:
            sessions[name] = _session(stream=True)
            sessions[name].speaker = InterruptibleSpeaker()
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
    session.speaker = InterruptibleSpeaker()
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
