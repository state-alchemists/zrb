"""The UI's view of the conversation: model, turn state, history, meters."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zrb.llm.agent.types import RequestUsage, RunUsage


class AnyUISession(ABC):
    """Which conversation is open, which model answers, and whether a turn runs."""

    @property
    @abstractmethod
    def llm_task(self) -> Any:
        """The `LLMTask` driving this UI, or None when it has none."""

    @llm_task.setter
    @abstractmethod
    def llm_task(self, value: Any) -> None: ...

    @property
    @abstractmethod
    def model(self) -> Any:
        """The model this UI is currently talking to, or None."""

    @model.setter
    @abstractmethod
    def model(self, value: Any) -> None: ...

    @property
    @abstractmethod
    def small_model(self) -> Any:
        """The `/model small ...` override this UI holds, or None."""

    @small_model.setter
    @abstractmethod
    def small_model(self, value: Any) -> None: ...

    @property
    @abstractmethod
    def multimodal_model(self) -> Any:
        """The `/model multimodal ...` override this UI holds, or None."""

    @multimodal_model.setter
    @abstractmethod
    def multimodal_model(self, value: Any) -> None: ...

    @property
    @abstractmethod
    def conversation_session_name(self) -> str:
        """The conversation this UI is attached to. Empty when it tracks none."""

    @conversation_session_name.setter
    @abstractmethod
    def conversation_session_name(self, value: str) -> None: ...

    @property
    @abstractmethod
    def plan_mode_active(self) -> bool:
        """Whether `/plan` is on. `MultiUI` both reads and writes this on its
        primary child to keep the badge in step with in-run mode changes."""

    @plan_mode_active.setter
    @abstractmethod
    def plan_mode_active(self, value: bool) -> None: ...

    @property
    @abstractmethod
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""

    @is_thinking.setter
    @abstractmethod
    def is_thinking(self, value: bool) -> None: ...

    @property
    @abstractmethod
    def is_turn_running(self) -> bool:
        """Whether a turn is running that `cancel_current_turn` would stop:
        this UI's own, or the one its `MultiUI` parent runs for it."""

    @abstractmethod
    def cancel_current_turn(self, reason: str, flush: bool = True) -> None:
        """Stop the turn the assistant is taking, as Esc does: release a
        pending confirmation, cancel the running turn and fire `Stop` with
        *reason* (who asked, e.g. ``"escape"``). With no turn running only
        the confirmation is released; a UI that never runs a turn and holds
        no confirmation does nothing. *flush* reaches the confirmation release;
        an exit passes ``False`` because the transcript is being torn down.
        """

    @property
    @abstractmethod
    def history_manager(self) -> Any:
        """This UI's conversation history manager, or None when it keeps none."""

    @property
    @abstractmethod
    def snapshot_manager(self) -> Any:
        """This UI's filesystem-snapshot manager, or None when it keeps none."""

    @abstractmethod
    def accumulate_usage(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """Fold one run's token totals into a session meter."""

    @abstractmethod
    def reset_context_usage(self) -> None:
        """Forget the context size, stale after `/compress`."""

    @property
    @abstractmethod
    def background_tasks(self) -> "set[asyncio.Task]":
        """Tasks this UI keeps referenced so they are not garbage collected.

        Callers mutate the returned set directly (`.add`, `.discard`), so an
        implementation must hand back the same set each time, not a copy.
        """

    @abstractmethod
    async def update_system_info(self) -> None:
        """Refresh the system and repository status line after a turn."""
