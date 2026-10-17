"""`enable_emotion`: read the emotion of the user's prompt and the model's
reply, and fire the `Emotion` hook with each.

The model's emotion is an emoji it is asked to open its reply with; a
capability (`reply.ReplyEmotion`) takes it out of the reply before anything
shows or keeps it, and keeps it as `current_reply_emotion` instead. The
user's is the tone dictation heard the prompt said in
(`InputProvenance.tone`), which the model reads in the live context. A hook
passes both on, e.g. to an avatar.

The prompt's tone is read by a `UserPromptSubmit` hook, which runs on a pool
thread, so it waits for the reply's stream to start and fires from the run's
event loop, just before the reply's own.
"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING

from zrb.llm.ambient_state import get_input_provenance
from zrb.llm.emotion.config import EmotionConfig
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import get_run_hook_manager
from zrb.llm.hook.types import HookEvent
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.util.feature_config import replace_feature_sessions, replace_registration

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.emotion.reply import ReplyEmotion
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.task.chat.task import LLMChatTask


def enable_emotion(task: "LLMChatTask", config: EmotionConfig | None = None) -> None:
    """Read the emotion of *task*'s prompts and replies, when ``enabled``,
    and fire the `Emotion` hook with each. Calling it again replaces the
    earlier call."""
    sessions = replace_feature_sessions(
        task,
        "emotion",
        lambda: EmotionSession((config or EmotionConfig()).resolve()),
        lambda session: session.close(),
    )

    def register_hooks(manager: "HookManager") -> None:
        sessions.get().register_hooks(manager)

    def create_capabilities(ctx: "AnyContext") -> "list[ReplyEmotion]":
        return sessions.get().create_capabilities()

    replace_registration(
        task,
        "emotion",
        [
            ("append_hook_factory", register_hooks),
            ("append_capability_factory", create_capabilities),
        ],
    )
    task.prompt_manager.add_live_context(
        "emotion", lambda ctx: sessions.get().create_live_context()
    )


class EmotionSession:
    """One chat session's emotion state: its prompt hook and the user's tone
    waiting to fire."""

    def __init__(self, config: EmotionConfig) -> None:
        self.is_enabled = bool(config.enabled)
        # Bound once, so `remove_hook` gets the same object `add_hook` got.
        self._prompt_hook = self.handle_user_prompt_submit
        self._managers: "weakref.WeakSet[HookManager]" = weakref.WeakSet()
        # The user's tone, stored by the prompt hook (on a pool thread) and
        # fired when the reply starts streaming (on the event loop).
        self._pending: list[tuple[str, str]] = []

    def register_hooks(self, manager: "HookManager") -> None:
        """Add this session's prompt hook to *manager*, once."""
        self.unregister_hooks(manager)
        if self.is_enabled:
            manager.add_hook(self._prompt_hook, events=[HookEvent.USER_PROMPT_SUBMIT])
            self._managers.add(manager)

    def unregister_hooks(self, manager: "HookManager") -> None:
        """Take this session's prompt hook back out of *manager*."""
        if manager in self._managers:
            manager.remove_hook(self._prompt_hook)
            self._managers.discard(manager)

    def close(self) -> None:
        for manager in list(self._managers):
            self.unregister_hooks(manager)

    def create_live_context(self) -> str:
        """Ask the model for an emoji opening each reply, while enabled."""
        return get_prompt("emotion_live") if self.is_enabled else ""

    def create_capabilities(self) -> "list[ReplyEmotion]":
        """The capability that strips the emoji from this run's reply, or
        none while disabled."""
        if not self.is_enabled:
            return []
        # lazy: heavy third-party — the capability is a pydantic-ai class.
        from zrb.llm.emotion.reply import ReplyEmotion

        return [ReplyEmotion(self.handle_reply_emotion, self.handle_stream_start)]

    async def handle_user_prompt_submit(self, context: HookContext) -> HookResult:
        """Store the tone dictation heard this prompt in, to fire when the
        reply starts streaming. It replaces a tone left unfired by an earlier
        turn that ended before streaming."""
        provenance = get_input_provenance()
        tone = provenance.tone if provenance is not None else ""
        self._pending = [("user", tone)] if tone else []
        return HookResult()

    async def handle_stream_start(self) -> None:
        """Fire the user's tone as the reply starts streaming."""
        pending, self._pending = self._pending, []
        await _fire(pending)

    async def handle_reply_emotion(self, emotion: str) -> None:
        """Fire the emotion the reply opens with."""
        await _fire([("assistant", emotion)])


async def _fire(emotions: list[tuple[str, str]]) -> None:
    manager = get_run_hook_manager()
    for source, emotion in emotions:
        await manager.execute_hooks(
            HookEvent.EMOTION,
            {"emotion": emotion, "source": source},
            emotion=emotion,
            emotion_source=source,
        )
