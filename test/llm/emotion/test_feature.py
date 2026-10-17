"""The emotion of prompts and replies, read and fired as the Emotion hook."""

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
        self.capability_factories = []

    def append_hook_factory(self, factory):
        factory(self.hook_manager)

    def append_capability_factory(self, factory):
        self.capability_factories.append(factory)

    def remove_capability_factory(self, factory):
        self.capability_factories.remove(factory)


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


def _fired(contexts):
    return [(c.emotion_source, c.emotion) for c in contexts]


@pytest.mark.asyncio
async def test_the_users_tone_fires_as_the_reply_starts_then_the_replys(fired):
    session = EmotionSession(EmotionConfig(enabled=True))
    await _submit(session, _said("angry"), "this is broken again")
    assert fired == []

    await session.handle_stream_start()
    await session.handle_reply_emotion("sad")

    assert _fired(fired) == [("user", "angry"), ("assistant", "sad")]


@pytest.mark.asyncio
async def test_an_emoji_typed_or_a_turn_without_a_tone_fires_nothing(fired):
    session = EmotionSession(EmotionConfig(enabled=True))
    await _submit(session, KEYBOARD_INPUT, "we shipped it 😊")
    await session.handle_stream_start()
    await _submit(session, DICTATION_INPUT, "we shipped it")
    await session.handle_stream_start()

    assert fired == []


@pytest.mark.asyncio
async def test_a_tone_a_turn_never_streamed_is_not_given_to_the_next(fired):
    session = EmotionSession(EmotionConfig(enabled=True))
    await _submit(session, _said("angry"), "fix it")
    await _submit(session, DICTATION_INPUT, "never mind")

    await session.handle_stream_start()

    assert fired == []


def test_a_disabled_session_adds_no_capability_and_no_prompt():
    session = EmotionSession(EmotionConfig(enabled=False))

    assert session.create_capabilities() == []
    assert session.create_live_context() == ""


def test_an_enabled_session_adds_the_reply_capability():
    from zrb.llm.emotion.reply import ReplyEmotion

    (capability,) = EmotionSession(EmotionConfig(enabled=True)).create_capabilities()

    assert isinstance(capability, ReplyEmotion)


def test_enable_emotion_twice_registers_once():
    task = PersistentHookTask()
    enable_emotion(task, EmotionConfig(enabled=True))
    enable_emotion(task, EmotionConfig(enabled=True))
    try:
        providers = task.prompt_manager.get_live_contexts()
        assert [name for name, _ in providers] == ["emotion"]
        assert "😊 happy" in providers[0][1](None)
        assert len(task.capability_factories) == 1
        assert len(task.capability_factories[0](None)) == 1
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
