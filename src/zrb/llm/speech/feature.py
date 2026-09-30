"""`enable_speech`: read replies, tool approvals and questions aloud.

Everything is spoken by one background thread per session, in order, so a hook
only queues text and returns. A long reply is cut at a sentence end, or
summarized by a model, and followed by a note that the rest is on screen.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import time
import weakref
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.speech.config import SpeechConfig
from zrb.llm.speech.player import IsStale, Speaker, is_speaking
from zrb.llm.speech.progress import ProgressNarrator, SpeechClock
from zrb.llm.speech.streamed_reply import StreamedReply
from zrb.llm.speech.text import clean_for_speech, fit_for_speech
from zrb.llm.util.feature_config import (
    current_session_key,
    get_session_ui,
    replace_feature_sessions,
    replace_registration,
)

if TYPE_CHECKING:
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.ui.base.ui import BaseUI

logger = logging.getLogger(__name__)

_QUESTION_NOTIFICATIONS = ("elicitation_dialog", "permission_prompt")
# The names the `LLM_HOOKS` allowlist knows speech's hooks by.
_HOOK_NAMES = ("handle_stop", "handle_permission_request", "handle_notification")


def enable_speech(
    task: "LLMTask | LLMChatTask", config: SpeechConfig | None = None
) -> None:
    """Speak *task*'s replies, approvals and questions, from the start of a
    session when ``enabled``. On an `LLMChatTask`, also add the command that
    switches speech on and off during a session. Calling it again replaces the
    earlier call.

    Speech rides on the hook subsystem, so `ZRB_HOOKS_ENABLED` off silences
    it; a warning says so at session start.
    """
    sessions = replace_feature_sessions(
        task,
        "speech",
        lambda: SpeechSession((config or SpeechConfig()).resolve()),
        lambda session: session.close(),
    )

    def register_hooks(manager: "HookManager") -> None:
        sessions.get().register_hooks(manager)

    def create_commands() -> "list[AnyCustomCommand]":
        return sessions.get().create_commands()

    def observe_stream(event: Any) -> None:
        sessions.get().handle_stream_event(event)

    registrations: list[tuple[str, Any]] = [("append_hook_factory", register_hooks)]
    if callable(getattr(task, "append_stream_observer", None)):
        registrations.append(("append_stream_observer", observe_stream))
    if callable(getattr(task, "append_custom_command", None)):
        registrations.append(("append_custom_command", create_commands))
    replace_registration(task, "speech", registrations)
    prompt_manager = getattr(task, "prompt_manager", None)
    if prompt_manager is not None:
        # Keyed by name, so enabling speech again replaces it.
        prompt_manager.add_live_context(
            "speech", lambda ctx: sessions.get().create_live_context()
        )


# Every live `SpeechSession`, by the chat session it speaks for, so dictation
# can silence the right one when the user talks over it.
_speech_sessions: "dict[str, weakref.WeakSet[SpeechSession]]" = {}


def pause_speech(session_key: str | None = None) -> None:
    """Hold what the chat session *session_key* (default: the one asking) is
    saying, for a user who may have started talking over it: `resume_speech`
    carries on, `interrupt_speech` drops it. Speech that cannot pause (a
    player program) is interrupted."""
    _for_each_session(session_key, lambda session: session.speaker.pause())


def resume_speech(session_key: str | None = None) -> None:
    """Carry on after `pause_speech`: what was heard was not the user."""
    _for_each_session(session_key, lambda session: session.speaker.resume())


def _for_each_session(
    session_key: str | None, act: Callable[["SpeechSession"], None]
) -> None:
    key = current_session_key() if session_key is None else session_key
    for session in list(_speech_sessions.get(key, ())):
        try:
            act(session)
        except Exception as exc:
            logger.warning(f"Speech control failed: {exc}")


def interrupt_speech(session_key: str | None = None) -> None:
    """Stop what the chat session *session_key* (default: the one asking) is
    saying and drop what it has queued, for a user who started talking over
    it. Speech after this is spoken as usual."""
    _for_each_session(session_key, lambda session: session.interrupt())


class SpeechSession:
    """The speaker and the hooks feeding it, for one resolved *config*."""

    def __init__(self, config: SpeechConfig) -> None:
        self._config = config
        self._events = {event.strip().lower() for event in config.events or []}
        # A task given a `hook_manager` shares it between sessions; each
        # session's hooks then see every session's events.
        self._session_key = current_session_key()
        _speech_sessions.setdefault(self._session_key, weakref.WeakSet()).add(self)
        # The bound methods handed to each manager, so they can be taken back
        # out: `remove_hook` matches on identity, and a bound method is a new
        # object on every attribute read.
        self._hooks: (
            "weakref.WeakKeyDictionary[HookManager, list[tuple[Any, list[HookEvent]]]]"
        ) = weakref.WeakKeyDictionary()
        self.speaker = Speaker(config)
        self.speaker.is_enabled = bool(config.enabled)
        self._clock = SpeechClock()
        self.streamed_reply = StreamedReply(
            self._say, config.max_chars or 0, config.on_screen_note or ""
        )
        self.progress = ProgressNarrator(
            self._say, self._seconds_since_said, config.progress_interval or 0
        )
        if not CFG.HOOKS_ENABLED:
            logger.warning(
                "Speech is delivered by the hook subsystem, which is off "
                "(ZRB_HOOKS_ENABLED), so nothing will be spoken."
            )
        hidden = set(_HOOK_NAMES) - set(CFG.LLM_HOOKS or _HOOK_NAMES)
        if hidden:
            logger.warning(
                "The ZRB_LLM_HOOKS allowlist leaves out speech's hooks "
                f"({', '.join(sorted(hidden))}), so those events are not spoken."
            )

    def register_hooks(self, manager: "HookManager") -> None:
        """Add this session's hooks to *manager*, taking out any it added to
        that manager before.

        A task holding one `HookManager` across runs has every factory
        re-applied on each run, so registering has to be idempotent or the
        second run would speak every reply twice.
        """
        self.unregister_hooks(manager)
        hooks: list[tuple[Any, list[HookEvent]]] = []
        if "reply" in self._events:
            hooks.append((self.handle_stop, [HookEvent.STOP]))
        if "approval" in self._events:
            hooks.append(
                (self.handle_permission_request, [HookEvent.PERMISSION_REQUEST])
            )
        if "question" in self._events:
            hooks.append((self.handle_notification, [HookEvent.NOTIFICATION]))
        for hook, events in hooks:
            manager.add_hook(hook, events=events)
        self._hooks[manager] = hooks

    def unregister_hooks(self, manager: "HookManager") -> None:
        """Take this session's hooks back out of *manager*."""
        for hook, _ in self._hooks.pop(manager, []):
            manager.remove_hook(hook)

    def close(self) -> None:
        """Take the hooks back out and stop the speaker."""
        for manager in list(self._hooks):
            self.unregister_hooks(manager)
        self.speaker.close()
        sessions = _speech_sessions.get(self._session_key)
        if sessions is not None:
            sessions.discard(self)
            if not sessions:
                _speech_sessions.pop(self._session_key, None)

    def interrupt(self) -> None:
        """Stop speaking now and say nothing more of the response being
        written; `interrupt_speech`."""
        self.speaker.interrupt()
        self.streamed_reply.mute_response()

    def create_commands(self) -> "list[AnyCustomCommand]":
        return [
            ActionCommand(
                command,
                self.toggle,
                description="Switch speech on or off",
                can_run_while_thinking=True,
            )
            for command in self._config.commands or []
        ]

    def toggle(self, kwargs: dict[str, str], ui: "BaseUI | None") -> str:
        self.speaker.is_enabled = not self.speaker.is_enabled
        if not self.speaker.is_enabled:
            self.speaker.clear()
            self.streamed_reply.reset()
        return f"🔊 Speech {'on' if self.speaker.is_enabled else 'off'}"

    def create_live_context(self) -> str:
        """Tell the model its reply is heard, while it is: a reply written to
        be read aloud opens with the answer instead of a table."""
        if self.speaker.is_enabled and "reply" in self._events:
            return get_prompt("speech_live")
        return ""

    def handle_stream_event(self, event: Any) -> None:
        """Speak the reply's sentences as they stream, when ``stream`` is on,
        and announce a tool call that starts after a silence, with
        ``progress``. Only the main run's events arrive: a sub-agent's run
        has no stream observers."""
        if not self.speaker.is_enabled:
            return
        # The reply first: text flushed at a tool call's start counts as
        # speech, so the call is not announced on top of it.
        if self._config.stream and "reply" in self._events:
            self.streamed_reply.handle_event(event)
        if "progress" in self._events:
            self.progress.handle_event(event)

    def _say(self, text: str, is_stale: IsStale = None) -> None:
        # Through `self.speaker` at call time, so a speaker replaced later is
        # the one that speaks.
        self._clock.mark()
        self.speaker.say(text, is_stale=is_stale)

    def _seconds_since_said(self) -> float:
        if is_speaking(self._config.lock_file or None):
            return 0.0
        return self._clock.seconds_since_said()

    async def handle_stop(self, context: HookContext) -> HookResult:
        """Speak the reply, but not a sub-agent's: only the main turn is for
        the user. A streamed reply only needs its last words spoken; one
        cancelled (Esc, a barge-in: the payload names a ``reason``) is not
        finished at all."""
        event_data = context.event_data if isinstance(context.event_data, dict) else {}
        if not self._is_own_session() or event_data.get("nested_run"):
            return HookResult(success=True)
        if event_data.get("reason"):
            self.streamed_reply.reset()
            self.speaker.clear()
            return HookResult(success=True)
        if self._config.stream:
            self.streamed_reply.flush()
            has_claimed_turn = self.streamed_reply.has_claimed_turn
            self.streamed_reply.reset()
            if has_claimed_turn:
                return HookResult(success=True)
        if context.last_assistant_message:
            self.say_reply(context.last_assistant_message)
        return HookResult(success=True)

    async def handle_permission_request(self, context: HookContext) -> HookResult:
        """Speak the approval request, unless it is answered first."""
        if self._is_own_session():
            self._say(
                describe_tool_call(context.tool_name, context.tool_input),
                is_stale=is_answered_since(get_session_ui(), time.monotonic()),
            )
        return HookResult(success=True)

    async def handle_notification(self, context: HookContext) -> HookResult:
        if (
            self._is_own_session()
            and context.notification_type in _QUESTION_NOTIFICATIONS
        ):
            question = self._fit(clean_for_speech(context.message or ""))
            self._say(question or "A question is waiting for your answer.")
        return HookResult(success=True)

    def _is_own_session(self) -> bool:
        return current_session_key() == self._session_key

    def say_reply(self, reply: str) -> None:
        """Speak *reply* in full if it fits, else shortened: summarized in the
        background when configured, cut at a sentence end otherwise."""
        spoken = clean_for_speech(reply)
        max_chars = self._config.max_chars or 0
        if max_chars <= 0 or len(spoken) <= max_chars or not self._config.summarize:
            self._say(self._fit(spoken))
            return
        # On the speaker's thread, not as a task on the running loop: a hook
        # runs on a loop of its own that is closed once the hook returns,
        # cancelling what is left on it.
        context = contextvars.copy_context()
        self.speaker.say_later(
            lambda: context.run(asyncio.run, self._create_summary(reply, spoken))
        )

    async def _create_summary(self, reply: str, spoken: str) -> str:
        try:
            summary = clean_for_speech(await self._summarize(reply))
        except Exception as exc:
            logger.warning(f"Speech summary failed, speaking the opening: {exc}")
            summary = ""
        if not summary:
            return self._fit(spoken)
        fitted = self._fit(summary)
        if fitted == summary:
            fitted = f"{summary} {self._config.on_screen_note or ''}".strip()
        return fitted

    async def _summarize(self, reply: str) -> str:
        # lazy: heavy transitive (pydantic_ai) via zrb.llm.agent.summarizer
        from zrb.llm.agent.summarizer import create_summarizer_agent

        agent = create_summarizer_agent(
            model=self._config.summary_model or None,
            system_prompt=get_prompt("speech_summarizer"),
        )
        result = await agent.run(reply)
        return str(result.output or "")

    def _fit(self, text: str) -> str:
        return fit_for_speech(
            text, self._config.max_chars or 0, self._config.on_screen_note or ""
        )


def is_answered_since(ui: Any, asked_at: float) -> Callable[[], bool]:
    """Whether a prompt *ui* showed at or after *asked_at* has been answered.
    The hook fires just before its prompt appears, so an older prompt
    answered meanwhile does not count; a UI that cannot say when its prompts
    appeared never reads as answered.
    """

    def is_answered() -> bool:
        is_answered_since = getattr(ui, "is_prompt_answered_since", None)
        return bool(is_answered_since and is_answered_since(asked_at))

    return is_answered


_TOOL_ACTIONS = {
    "Write": "write a file",
    "Edit": "edit a file",
    "NotebookEdit": "edit a notebook",
    "Shell": "run a shell command",
    "Bash": "run a shell command",
    "DelegateToAgent": "delegate work to a sub-agent",
    "DelegateToAgentBackground": "delegate background work to a sub-agent",
}
_TARGET_KEYS = ("path", "file_path", "command", "notebook_path")


def describe_tool_call(tool: str | None, args: dict[str, Any] | None) -> str:
    """A spoken approval request. A template, not a model call: the user is
    waiting on it."""
    action = _TOOL_ACTIONS.get(
        tool or "", f"use the {tool} tool" if tool else "run a tool"
    )
    target = ""
    for key in _TARGET_KEYS:
        value = (args or {}).get(key)
        if isinstance(value, str) and value.strip():
            target = " " + value.strip()[:80]
            break
    return f"I need to {action}{target}. I need your approval."
