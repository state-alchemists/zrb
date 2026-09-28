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
from zrb.llm.speech.config import SpeechConfig
from zrb.llm.speech.player import Speaker
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

    registrations: list[tuple[str, Any]] = [("append_hook_factory", register_hooks)]
    if callable(getattr(task, "append_custom_command", None)):
        registrations.append(("append_custom_command", create_commands))
    replace_registration(task, "speech", registrations)


class SpeechSession:
    """The speaker and the hooks feeding it, for one resolved *config*."""

    def __init__(self, config: SpeechConfig) -> None:
        self._config = config
        self._events = {event.strip().lower() for event in config.events or []}
        # A task given a `hook_manager` shares it between sessions; each
        # session's hooks then see every session's events.
        self._session_key = current_session_key()
        # The bound methods handed to each manager, so they can be taken back
        # out: `remove_hook` matches on identity, and a bound method is a new
        # object on every attribute read.
        self._hooks: (
            "weakref.WeakKeyDictionary[HookManager, list[tuple[Any, list[HookEvent]]]]"
        ) = weakref.WeakKeyDictionary()
        self.speaker = Speaker(config)
        self.speaker.is_enabled = bool(config.enabled)
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
        return f"🔊 Speech {'on' if self.speaker.is_enabled else 'off'}"

    async def handle_stop(self, context: HookContext) -> HookResult:
        """Speak the reply, but not a sub-agent's: only the main turn is for
        the user."""
        event_data = context.event_data if isinstance(context.event_data, dict) else {}
        if (
            self._is_own_session()
            and not event_data.get("nested_run")
            and context.last_assistant_message
        ):
            self.say_reply(context.last_assistant_message)
        return HookResult(success=True)

    async def handle_permission_request(self, context: HookContext) -> HookResult:
        """Speak the approval request, unless it is answered first."""
        if self._is_own_session():
            self.speaker.say(
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
            self.speaker.say(question or "A question is waiting for your answer.")
        return HookResult(success=True)

    def _is_own_session(self) -> bool:
        return current_session_key() == self._session_key

    def say_reply(self, reply: str) -> None:
        """Speak *reply* in full if it fits, else shortened: summarized in the
        background when configured, cut at a sentence end otherwise."""
        spoken = clean_for_speech(reply)
        max_chars = self._config.max_chars or 0
        if max_chars <= 0 or len(spoken) <= max_chars or not self._config.summarize:
            self.speaker.say(self._fit(spoken))
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
        from zrb.llm.prompt.prompt import get_prompt

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
