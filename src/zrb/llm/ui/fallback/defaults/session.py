"""Inert session role: a UI that tracks no conversation of its own.

Every member reports absence — no model, no history, no snapshots, no turn
running — rather than raising, so `MultiUI` and the renderer can read them
unconditionally on a secondary UI. The mutable ones round-trip, so a caller may
install a model or a task on a UI that does not otherwise track it.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from zrb.llm.agent.types import RequestUsage, RunUsage
    from zrb.llm.ui.any_ui_session import AnyUISession


class UISessionDefaults:
    """The session role for a UI that keeps none of this state."""

    _uidefaults_is_thinking: bool = False
    _uidefaults_llm_task: Any = None
    _uidefaults_model: Any = None
    # None, not set(): a mutable class attribute would be shared by instances.
    _uidefaults_background_tasks: "set[asyncio.Task] | None" = None
    _uidefaults_small_model: Any = None
    _uidefaults_multimodal_model: Any = None
    _uidefaults_conversation_session_name: str = ""
    _uidefaults_plan_mode_active: bool = False

    @property
    def session(self) -> "AnyUISession":
        """A UI that tracks its own conversation is its own session.

        The state the role names — the model, the open conversation, the turn
        flags, the meters — lives on the UI itself, because a subclass that
        overrides one of those members has to keep answering for it. Handing
        out a second object that forwards to the host would put that state in
        two places and let the two disagree; the role is a narrowing of the
        object, not a copy of it.
        """
        return cast("AnyUISession", self)

    @property
    def is_thinking(self) -> bool:
        return self._uidefaults_is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool) -> None:
        self._uidefaults_is_thinking = value

    @property
    def llm_task(self) -> Any:
        return self._uidefaults_llm_task

    @llm_task.setter
    def llm_task(self, value: Any) -> None:
        self._uidefaults_llm_task = value

    @property
    def model(self) -> Any:
        return self._uidefaults_model

    @model.setter
    def model(self, value: Any) -> None:
        self._uidefaults_model = value

    @property
    def small_model(self) -> Any:
        return self._uidefaults_small_model

    @small_model.setter
    def small_model(self, value: Any) -> None:
        self._uidefaults_small_model = value

    @property
    def multimodal_model(self) -> Any:
        return self._uidefaults_multimodal_model

    @multimodal_model.setter
    def multimodal_model(self, value: Any) -> None:
        self._uidefaults_multimodal_model = value

    @property
    def conversation_session_name(self) -> str:
        return self._uidefaults_conversation_session_name

    @conversation_session_name.setter
    def conversation_session_name(self, value: str) -> None:
        self._uidefaults_conversation_session_name = value

    @property
    def plan_mode_active(self) -> bool:
        return self._uidefaults_plan_mode_active

    @plan_mode_active.setter
    def plan_mode_active(self, value: bool) -> None:
        self._uidefaults_plan_mode_active = value

    @property
    def snapshot_manager(self) -> Any:
        """No snapshots of its own, so nothing to rewind to."""
        return None

    @property
    def history_manager(self) -> Any:
        """No history of its own; the session's manager lives on the primary."""
        return None

    @property
    def background_tasks(self) -> "set[asyncio.Task]":
        """One mutable set per instance, created on first access."""
        if self._uidefaults_background_tasks is None:
            self._uidefaults_background_tasks = set()
        return self._uidefaults_background_tasks

    @property
    def is_turn_running(self) -> bool:
        """No turn of its own to run."""
        return False

    def cancel_current_turn(self, reason: str) -> None:
        """No turn of its own to cancel."""

    def accumulate_usage(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """No session meter to fold usage into."""

    def reset_context_usage(self) -> None:
        """No context size to forget."""

    async def update_system_info(self) -> None:
        """No status line to refresh."""
