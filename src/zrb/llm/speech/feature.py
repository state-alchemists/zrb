"""`enable_speech`: read replies, tool approvals and questions aloud.

Everything is spoken by one background thread per session, in order, so a hook
only queues text and returns. A reply is read whole, however long it is,
unless ``summarize_above_chars`` is set: a longer one is then spoken as the
small model's summary, once the turn ends.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import threading
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
from zrb.llm.speech.summary import (
    ResolutionSlot,
    SpeechSummaryError,
    summarize_for_speech,
)
from zrb.llm.speech.text import (
    clean_for_speech,
    fill_template,
    match_tool_phrase,
)
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
    from zrb.llm.ui.any_ui import AnyUI
    from zrb.llm.ui.base.ui import BaseUI

logger = logging.getLogger(__name__)

_QUESTION_NOTIFICATIONS = ("elicitation_dialog",)
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

    registrations: list[tuple[str, Any]] = [
        ("append_hook_factory", register_hooks),
        ("append_stream_observer", observe_stream),
    ]
    # Only `LLMChatTask` takes custom commands; `LLMTask` has none.
    if callable(getattr(task, "append_custom_command", None)):
        registrations.append(("append_custom_command", create_commands))
    replace_registration(task, "speech", registrations)
    # Keyed by name, so enabling speech again replaces it.
    task.prompt_manager.add_live_context(
        "speech", lambda ctx: sessions.get().create_live_context()
    )


# Every live `SpeechSession`, by the chat session it speaks for, so dictation
# can silence the right one when the user talks over it.
_speech_sessions: "dict[str, weakref.WeakSet[SpeechSession]]" = {}


def pause_speech(session_key: str | None = None) -> None:
    """Hold what the chat session *session_key* (default: the one asking) is
    saying, for a user who may have started talking over it: `resume_speech`
    carries on, `interrupt_speech` drops it. A sentence that cannot pause
    (a player program plays it) is stopped, and the rest held as usual, so
    `resume_speech` carries on with the next sentence."""
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
        # Bumped whenever what is pending stops mattering: an interrupt, or a
        # newer reply than a summary still being made.
        self._generation = 0
        self._resolution_slot = ResolutionSlot()
        self.streamed_reply = StreamedReply(self._say)
        self.progress = ProgressNarrator(
            self._say,
            self._seconds_since_said,
            config.progress_interval or 0,
            silent_tools=config.progress_silent_tools,
            phrases=config.progress_phrases,
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
        if "reply" in self._events or "progress" in self._events:
            # A `progress`-only session needs this hook too: it is where a
            # turn's still-queued progress lines are invalidated, and a session
            # can narrate tool calls without ever speaking the reply.
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
        """Take the hooks back out and stop the speaker. A summary still being
        made is dropped when it finishes."""
        self._generation += 1
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
        self._generation += 1
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
            self._generation += 1
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
        if self.is_streaming_reply and "reply" in self._events:
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
        finished at all.

        Also drops the progress lines the turn still has queued, which is why a
        `progress`-only session gets this hook even though it speaks no reply."""
        event_data = context.event_data if isinstance(context.event_data, dict) else {}
        if not self._is_own_session() or event_data.get("nested_run"):
            return HookResult(success=True)
        self.progress.reset()
        # A summary still being made belongs to an earlier turn, whatever this
        # one goes on to say; one `say_reply` starts is for the new generation.
        self._generation += 1
        if event_data.get("reason"):
            if "reply" in self._events:
                # Cancelled: stop the sentence playing too, not only the queue.
                self.streamed_reply.reset()
            # Whatever was being said belongs to the cancelled turn, and with
            # only `progress` on that is a progress line, not a reply.
            self.speaker.interrupt()
            return HookResult(success=True)
        if "reply" not in self._events:
            # Nothing to say here: a queued progress line is already stale.
            return HookResult(success=True)
        if self.is_streaming_reply:
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
                describe_tool_call(
                    context.tool_name,
                    context.tool_input,
                    message=self._config.approval_message,
                    target_keys=self._config.approval_target_keys,
                    target_max_chars=self._config.approval_target_max_chars,
                    actions=self._config.approval_actions,
                ),
                is_stale=is_answered_since(get_session_ui(), time.monotonic()),
            )
        return HookResult(success=True)

    async def handle_notification(self, context: HookContext) -> HookResult:
        if (
            self._is_own_session()
            and context.notification_type in _QUESTION_NOTIFICATIONS
        ):
            question = clean_for_speech(context.message or "")
            self._say(question or self._config.question_message or "")
        return HookResult(success=True)

    def _is_own_session(self) -> bool:
        return current_session_key() == self._session_key

    @property
    def is_streaming_reply(self) -> bool:
        """Whether the reply is spoken a sentence at a time as it is written.
        A reply that may be summarized waits for its last word, so it is not."""
        return bool(self._config.stream) and not self._summarize_above_chars

    @property
    def _summarize_above_chars(self) -> int:
        return max(self._config.summarize_above_chars or 0, 0)

    def say_reply(self, reply: str) -> None:
        """Speak *reply*: whole, or as a summary when its speakable text is
        longer than ``summarize_above_chars``. The summary is made on a thread of
        its own, so neither the turn nor the speaker's queue waits for the
        model, and it is dropped if speech is interrupted or a newer reply comes
        first."""
        self._generation += 1
        text = clean_for_speech(reply)
        if not self._summarize_above_chars or len(text) <= self._summarize_above_chars:
            self._say(text)
            return
        # The model settings a run scopes live in context variables, which a
        # new thread does not inherit.
        context = contextvars.copy_context()
        interrupts = self._generation
        threading.Thread(
            target=context.run,
            args=(self._say_summary, text, lambda: self._generation != interrupts),
            daemon=True,
        ).start()

    def _say_summary(self, text: str, is_stale: IsStale) -> None:
        self._say(self._summarize(text), is_stale=is_stale)

    def _summarize(self, text: str) -> str:
        try:
            return asyncio.run(
                summarize_for_speech(
                    text,
                    self._config.summary_model or None,
                    self._config.summary_timeout or 0,
                    self._resolution_slot,
                )
            )
        except SpeechSummaryError as exc:
            logger.warning(f"Reading the reply whole, not summarized: {exc}")
            return text


def is_answered_since(ui: "AnyUI | None", asked_at: float) -> Callable[[], bool]:
    """Whether a prompt *ui* showed at or after *asked_at* has been answered.
    The hook fires just before its prompt appears, so an older prompt
    answered meanwhile does not count; no UI, or one that cannot say when its
    prompts appeared, never reads as answered.
    """

    def is_answered() -> bool:
        return ui is not None and ui.is_prompt_answered_since(asked_at)

    return is_answered


def describe_tool_call(
    tool: str | None,
    args: dict[str, Any] | None,
    message: str | None = None,
    target_keys: list[str] | None = None,
    target_max_chars: int | None = None,
    actions: dict[str, str] | None = None,
) -> str:
    """A spoken approval request, from *message* with ``{action}`` (the
    first of *actions* whose pattern matches *tool*, else the tool's name)
    and ``{target}`` (the first of *target_keys* among *args*, cut to
    *target_max_chars*). A template, not a model call: the user is waiting
    on it. Each left ``None`` is read from `CFG.LLM_SPEECH_APPROVAL_*`."""
    if message is None:
        message = CFG.LLM_SPEECH_APPROVAL_MESSAGE
    if target_keys is None:
        target_keys = CFG.LLM_SPEECH_APPROVAL_TARGET_KEYS
    if target_max_chars is None:
        target_max_chars = CFG.LLM_SPEECH_APPROVAL_TARGET_MAX_CHARS
    if actions is None:
        actions = CFG.LLM_SPEECH_APPROVAL_ACTIONS
    action = match_tool_phrase(tool, actions)
    if action is None:
        action = tool or ""
    target = ""
    for key in target_keys if target_max_chars > 0 else []:
        value = (args or {}).get(key)
        if isinstance(value, str) and value.strip():
            target = " " + value.strip()[:target_max_chars]
            break
    return fill_template(message, action=action, target=target)
