"""The emotion of prompts and replies, read and fired as the Emotion hook."""

from types import SimpleNamespace

import pytest

from zrb.llm.ambient_state import input_provenance
from zrb.llm.emotion import EmotionConfig, enable_emotion
from zrb.llm.emotion.feature import EmotionSession
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.input_source import DICTATION_INPUT, KEYBOARD_INPUT, InputProvenance
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.util.feature_config import close_feature_sessions


class PersistentHookTask:
    def __init__(self):
        self.hook_manager = HookManager(search_dirs=[])
        self.prompt_manager = PromptManager(include_sections=[])
        self.stream_observers = []

    def append_hook_factory(self, factory):
        factory(self.hook_manager)

    def append_stream_observer(self, observer):
        self.stream_observers.append(observer)

    def remove_stream_observer(self, observer):
        self.stream_observers.remove(observer)


def _text_start(content: str):
    return SimpleNamespace(
        event_kind="part_start", part=SimpleNamespace(part_kind="text", content=content)
    )


def _text_delta(content: str):
    return SimpleNamespace(
        event_kind="part_delta",
        delta=SimpleNamespace(part_delta_kind="text", content_delta=content),
    )


def _prompt(text: str) -> HookContext:
    return HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={}, prompt=text)


def _said(tone: str) -> InputProvenance:
    return InputProvenance(
        "microphone", "dictation", transcription=True, tone=tone, tone_score=0.9
    )


async def _submit(session: EmotionSession, source: InputProvenance, text: str):
    token = input_provenance.set(source)
    try:
        await session.handle_user_prompt_submit(_prompt(text))
    finally:
        input_provenance.reset(token)


@pytest.fixture
def fired(monkeypatch):
    """Emotion hook contexts fired through the run's hook manager."""
    manager = HookManager(search_dirs=[])
    contexts: list[HookContext] = []

    async def record(context: HookContext) -> HookResult:
        contexts.append(context)
        return HookResult()

    manager.add_hook(record, events=[HookEvent.EMOTION])
    monkeypatch.setattr("zrb.llm.emotion.feature.get_run_hook_manager", lambda: manager)
    return contexts


async def _feed(session: EmotionSession, *events) -> None:
    for event in events:
        fire = session.handle_stream_event(event)
        if fire is not None:
            await fire


def _fired(contexts):
    return [(c.emotion_source, c.emotion) for c in contexts]


@pytest.mark.asyncio
async def test_the_emoji_a_reply_opens_with_fires_its_emotion(fired):
    session = EmotionSession(EmotionConfig(enabled=True))

    await _feed(session, _text_start(""), _text_delta(" "), _text_delta("😊 Done."))

    assert _fired(fired) == [("assistant", "happy")]


@pytest.mark.asyncio
async def test_a_reply_without_an_emoji_fires_nothing(fired):
    session = EmotionSession(EmotionConfig(enabled=True))

    await _feed(session, _text_start("Done 😊"), _text_delta(" more"))

    assert fired == []


@pytest.mark.asyncio
async def test_the_tone_dictation_heard_fires_with_the_replys_first_event(fired):
    session = EmotionSession(EmotionConfig(enabled=True))
    await _submit(session, _said("angry"), "this is broken again")
    assert fired == []

    await _feed(session, _text_start("😢 Sorry about that."))

    assert _fired(fired) == [("user", "angry"), ("assistant", "sad")]


@pytest.mark.asyncio
async def test_each_text_part_is_read_once(fired):
    session = EmotionSession(EmotionConfig(enabled=True))

    await _feed(
        session, _text_start("😮 Oh."), _text_delta(" 😊"), _text_start("😌 Ok.")
    )

    assert _fired(fired) == [("assistant", "surprised"), ("assistant", "relaxed")]


@pytest.mark.asyncio
async def test_a_disabled_session_reads_nothing(fired):
    session = EmotionSession(EmotionConfig(enabled=False))

    await _feed(session, _text_start("😊 Done."))

    assert fired == []
    assert session.create_live_context() == ""


@pytest.mark.asyncio
async def test_the_emotion_hook_reaches_a_hook_registered_on_the_task(monkeypatch):
    task = PersistentHookTask()
    contexts: list[HookContext] = []

    async def record(context: HookContext) -> HookResult:
        contexts.append(context)
        return HookResult()

    task.hook_manager.add_hook(record, events=[HookEvent.EMOTION])
    monkeypatch.setattr(
        "zrb.llm.emotion.feature.get_run_hook_manager", lambda: task.hook_manager
    )
    enable_emotion(task, EmotionConfig(enabled=True))
    token = input_provenance.set(_said("happy"))
    try:
        await task.hook_manager.execute_hooks(
            HookEvent.USER_PROMPT_SUBMIT, {}, prompt="we did it"
        )
        await task.stream_observers[0](_text_start("😊 Great!"))
    finally:
        input_provenance.reset(token)
        close_feature_sessions("")

    assert _fired(contexts) == [("user", "happy"), ("assistant", "happy")]
    assert contexts[0].to_claude_json()["emotion_source"] == "user"


def test_enable_emotion_twice_registers_once():
    task = PersistentHookTask()
    enable_emotion(task, EmotionConfig(enabled=True))
    enable_emotion(task, EmotionConfig(enabled=True))
    try:
        providers = task.prompt_manager.get_live_contexts()
        assert [name for name, _ in providers] == ["emotion"]
        assert "😊 happy" in providers[0][1](None)
        assert len(task.stream_observers) == 1
    finally:
        close_feature_sessions("")


def test_closing_takes_the_prompt_hook_back_out():
    manager = HookManager(search_dirs=[])
    session = EmotionSession(EmotionConfig(enabled=True))
    session.register_hooks(manager)
    session.register_hooks(manager)
    assert len(manager.registry.get_hooks(HookEvent.USER_PROMPT_SUBMIT)) == 1

    session.close()

    assert manager.registry.get_hooks(HookEvent.USER_PROMPT_SUBMIT) == []


@pytest.mark.asyncio
async def test_an_emoji_typed_or_a_turn_without_a_tone_fires_nothing(fired):
    session = EmotionSession(EmotionConfig(enabled=True))
    await _submit(session, KEYBOARD_INPUT, "we shipped it 😊")
    await _submit(session, DICTATION_INPUT, "we shipped it")

    await _feed(session, _text_start("Done."))

    assert fired == []


@pytest.mark.asyncio
async def test_a_tone_a_turn_never_streamed_is_not_given_to_the_next(fired):
    session = EmotionSession(EmotionConfig(enabled=True))
    await _submit(session, _said("angry"), "fix it")
    await _submit(session, DICTATION_INPUT, "never mind")

    await _feed(session, _text_start("🙂 Okay."))

    assert _fired(fired) == [("assistant", "neutral")]
