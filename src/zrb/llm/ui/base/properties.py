"""Pure attribute-accessor properties for `BaseUI`.

Extracted from `base/ui.py` to keep that class focused on behavior. Every
property here is a thin getter/setter over `self._owner._<attr>` — a slot set
in `BaseUI.__init__` — with no logic or side effects (those stay in
`base/ui.py`). Composed into `BaseUI` as `self._properties`, taking the owner
so callers keep reading the same public names (e.g. `ui.exit_commands`)
through `BaseUI`'s delegators.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Callable
from typing import TYPE_CHECKING, Any

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI


class BaseUIProperties:
    """Pure attribute accessors for BaseUI (no logic, no side effects)."""

    def __init__(self, owner: "BaseUI") -> None:
        self._owner = owner

    @property
    def llm_task(self) -> Any:
        """Get the LLM task."""
        return self._owner._llm_task

    @llm_task.setter
    def llm_task(self, value: Any):
        """Set the LLM task."""
        self._owner._llm_task = value

    @property
    def model(self) -> Any:
        """Get the current model."""
        return self._owner._model

    @model.setter
    def model(self, value: Any):
        """Set the model."""
        self._owner._model = value

    @property
    def small_model(self) -> Any:
        """Get the current small model."""
        return self._owner._small_model

    @small_model.setter
    def small_model(self, value: Any):
        """Set the small model."""
        self._owner._small_model = value

    @property
    def multimodal_model(self) -> Any:
        """Get the current multimodal model."""
        return self._owner._multimodal_model

    @multimodal_model.setter
    def multimodal_model(self, value: Any):
        """Set the multimodal model."""
        self._owner._multimodal_model = value

    @property
    def conversation_session_name(self) -> str:
        """Get the conversation session name."""
        return self._owner._conversation_session_name

    @conversation_session_name.setter
    def conversation_session_name(self, value: str):
        """Set the conversation session name."""
        self._owner._conversation_session_name = value

    @property
    def triggers(self) -> list[Callable[[], AsyncIterable[Any]]]:
        return self._owner._triggers

    @triggers.setter
    def triggers(self, value: list[Callable[[], AsyncIterable[Any]]]):
        self._owner._triggers = value

    @property
    def last_output(self) -> str:
        if self._owner._last_result_data is None:
            return ""
        return self._owner._last_result_data

    @property
    def assistant_name(self) -> str:
        """Get the assistant name."""
        return self._owner._assistant_name

    @property
    def initial_message(self) -> Any:
        """Get the initial message."""
        return self._owner._initial_message

    @property
    def exit_commands(self) -> list[str]:
        """Get the list of exit commands."""
        return self._owner._exit_commands

    @property
    def info_commands(self) -> list[str]:
        """Get the list of info/help commands."""
        return self._owner._info_commands

    @property
    def save_commands(self) -> list[str]:
        """Get the list of save commands."""
        return self._owner._save_commands

    @property
    def load_commands(self) -> list[str]:
        """Get the list of load commands."""
        return self._owner._load_commands

    @property
    def attach_commands(self) -> list[str]:
        """Get the list of attach commands."""
        return self._owner._attach_commands

    @property
    def photo_commands(self) -> list[str]:
        """Get the list of photo capture commands."""
        return self._owner._photo_commands

    @property
    def redirect_output_commands(self) -> list[str]:
        """Get the list of redirect output commands."""
        return self._owner._redirect_output_commands

    @property
    def yolo_toggle_commands(self) -> list[str]:
        """Get the list of yolo toggle commands."""
        return self._owner._yolo_toggle_commands

    @property
    def set_model_commands(self) -> list[str]:
        """Get the list of set model commands."""
        return self._owner._set_model_commands

    @property
    def exec_commands(self) -> list[str]:
        """Get the list of exec commands."""
        return self._owner._exec_commands

    @property
    def custom_commands(self) -> list[AnyCustomCommand]:
        """Get the list of custom commands."""
        return self._owner._custom_commands

    @property
    def summarize_commands(self) -> list[str]:
        """Get the list of summarize commands."""
        return self._owner._summarize_commands

    @property
    def history_manager(self) -> Any:
        """Public read accessor for the conversation history manager."""
        return self._owner._history_manager

    @property
    def snapshot_manager(self) -> Any:
        """Public read accessor for the snapshot manager (may be None)."""
        return self._owner._snapshot_manager

    @property
    def background_tasks(self) -> Any:
        """Public read accessor for the background-task set."""
        return self._owner._background_tasks

    @property
    def confirmation_output_buffer(self) -> list[str]:
        """Public read accessor for the buffered output held during confirmation."""
        return self._owner._confirmation_output_buffer

    @property
    def pending_attachments(self) -> list[Any]:
        """Public read accessor for attachments queued for the next turn."""
        return self._owner._pending_attachments

    @property
    def plan_mode_active(self) -> bool:
        """Whether plan mode is currently active."""
        return self._owner._plan_mode_active

    @plan_mode_active.setter
    def plan_mode_active(self, value: bool):
        self._owner._plan_mode_active = value

    @property
    def voice_mode_active(self) -> bool:
        """Whether voice dictation mode is currently active."""
        return self._owner._voice_mode_active

    @voice_mode_active.setter
    def voice_mode_active(self, value: bool):
        self._owner._voice_mode_active = value

    @property
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""
        return self._owner._is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool):
        self._owner._is_thinking = value

    @property
    def message_queue(self) -> Any:
        """Public read accessor for the pending-message queue."""
        return self._owner._message_queue
