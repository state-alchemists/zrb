"""`enable_emotion`: read the emotion of the user's prompt and the model's
reply, and fire the `Emotion` hook with each.

The model's emotion is an emoji it is asked to open its reply with
(`label`), which the user sees. The user's is the tone dictation heard the
prompt said in (`InputProvenance.tone`), which the model reads in the live
context. A hook passes both on, e.g. to an avatar.

The prompt's tone is read by a `UserPromptSubmit` hook, which runs on a pool
thread, so it waits for the reply's first stream event and fires from the
run's event loop with the reply's own.
"""

from __future__ import annotations

import weakref
from collections.abc import Awaitable
from typing import TYPE_CHECKING

from zrb.llm.ambient_state import get_input_provenance
from zrb.llm.emotion.config import EmotionConfig
from zrb.llm.emotion.label import ReplyOpening
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import get_run_hook_manager
from zrb.llm.hook.types import HookEvent
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.util.feature_config import replace_feature_sessions, replace_registration

if TYPE_CHECKING:
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.task.llm_task import LLMTask


def enable_emotion(
    task: "LLMTask | LLMChatTask", config: EmotionConfig | None = None
) -> None:
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

    def observe_stream(event: object) -> Awaitable[None] | None:
        return sessions.get().handle_stream_event(event)

    replace_registration(
        task,
        "emotion",
        [
            ("append_hook_factory", register_hooks),
            ("append_stream_observer", observe_stream),
        ],
    )
    task.prompt_manager.add_live_context(
        "emotion", lambda ctx: sessions.get().create_live_context()
    )


class EmotionSession:
    """The emotions one chat session has read and not yet fired."""

    def __init__(self, config: EmotionConfig) -> None:
        self.is_enabled = bool(config.enabled)
        # Kept, so `remove_hook` gets back the object `add_hook` was given.
        self._prompt_hook = self.handle_user_prompt_submit
        self._managers: "weakref.WeakSet[HookManager]" = weakref.WeakSet()
        # (source, emotion) pairs to fire; the prompt hook appends from a
        # pool thread, the stream observer takes them on the event loop.
        self._pending: list[tuple[str, str]] = []
        self._opening = ReplyOpening()

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

    async def handle_user_prompt_submit(self, context: HookContext) -> HookResult:
        """Hold the tone dictation heard the prompt in, for the reply to fire.
        It replaces whatever an earlier turn left unfired (one that ended
        before streaming anything), which is not this turn's."""
        provenance = get_input_provenance()
        tone = provenance.tone if provenance is not None else ""
        self._pending = [("user", tone)] if tone else []
        return HookResult()

    def handle_stream_event(self, event: object) -> Awaitable[None] | None:
        """Read the emotion a reply opens with, and fire what is pending."""
        if not self.is_enabled:
            return None
        emotion = self._opening.read(event)
        if emotion is not None:
            self._pending.append(("assistant", emotion))
        if not self._pending:
            return None
        pending, self._pending = self._pending, []
        return _fire(pending)


async def _fire(emotions: list[tuple[str, str]]) -> None:
    manager = get_run_hook_manager()
    for source, emotion in emotions:
        await manager.execute_hooks(
            HookEvent.EMOTION,
            {"emotion": emotion, "source": source},
            emotion=emotion,
            emotion_source=source,
        )
