"""Pure attribute-accessor properties for `BaseUI`.

Extracted from `base/ui.py` to keep that class focused on behavior. Every
property here is a thin getter/setter over `self._base_ui._<attr>` — a slot
set in `BaseUI.__init__` — with no logic or side effects (those stay in
`base/ui.py`). Composed into `BaseUI` as `self._properties`, taking the
`BaseUI` reference so callers keep reading the same public names (e.g.
`ui.exit_commands`) through `BaseUI`'s delegators.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Callable
from typing import TYPE_CHECKING, Any

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI


class BaseUIProperties:
    """Pure attribute accessors for BaseUI (no logic, no side effects)."""

    def __init__(self, base_ui: "BaseUI") -> None:
        self._base_ui = base_ui

    @property
    def llm_task(self) -> Any:
        """Get the LLM task."""
        return self._base_ui._llm_task

    @llm_task.setter
    def llm_task(self, value: Any):
        """Set the LLM task."""
        self._base_ui._llm_task = value

    @property
    def model(self) -> Any:
        """Get the current model."""
        return self._base_ui._model

    @model.setter
    def model(self, value: Any):
        """Set the model."""
        self._base_ui._model = value

    @property
    def small_model(self) -> Any:
        """Get the current small model."""
        return self._base_ui._small_model

    @small_model.setter
    def small_model(self, value: Any):
        """Set the small model."""
        self._base_ui._small_model = value

    @property
    def multimodal_model(self) -> Any:
        """Get the current multimodal model."""
        return self._base_ui._multimodal_model

    @multimodal_model.setter
    def multimodal_model(self, value: Any):
        """Set the multimodal model."""
        self._base_ui._multimodal_model = value

    @property
    def conversation_session_name(self) -> str:
        """Get the conversation session name."""
        return self._base_ui._conversation_session_name

    @conversation_session_name.setter
    def conversation_session_name(self, value: str):
        """Set the conversation session name."""
        self._base_ui._conversation_session_name = value

    @property
    def triggers(self) -> list[Callable[[], AsyncIterable[Any]]]:
        return self._base_ui._triggers

    @triggers.setter
    def triggers(self, value: list[Callable[[], AsyncIterable[Any]]]):
        self._base_ui._triggers = value

    @property
    def last_output(self) -> str:
        if self._base_ui._last_result_data is None:
            return ""
        return self._base_ui._last_result_data

    @property
    def assistant_name(self) -> str:
        """Get the assistant name."""
        return self._base_ui._assistant_name

    @property
    def initial_message(self) -> Any:
        """Get the initial message."""
        return self._base_ui._initial_message

    @property
    def exit_commands(self) -> list[str]:
        """Get the list of exit commands."""
        return self._base_ui._exit_commands

    @property
    def info_commands(self) -> list[str]:
        """Get the list of info/help commands."""
        return self._base_ui._info_commands

    @property
    def save_commands(self) -> list[str]:
        """Get the list of save commands."""
        return self._base_ui._save_commands

    @property
    def load_commands(self) -> list[str]:
        """Get the list of load commands."""
        return self._base_ui._load_commands

    @property
    def attach_commands(self) -> list[str]:
        """Get the list of attach commands."""
        return self._base_ui._attach_commands

    @property
    def photo_commands(self) -> list[str]:
        """Get the list of photo capture commands."""
        return self._base_ui._photo_commands

    @property
    def redirect_output_commands(self) -> list[str]:
        """Get the list of redirect output commands."""
        return self._base_ui._redirect_output_commands

    @property
    def yolo_toggle_commands(self) -> list[str]:
        """Get the list of yolo toggle commands."""
        return self._base_ui._yolo_toggle_commands

    @property
    def set_model_commands(self) -> list[str]:
        """Get the list of set model commands."""
        return self._base_ui._set_model_commands

    @property
    def exec_commands(self) -> list[str]:
        """Get the list of exec commands."""
        return self._base_ui._exec_commands

    @property
    def custom_commands(self) -> list[AnyCustomCommand]:
        """Get the list of custom commands."""
        return self._base_ui._custom_commands

    @property
    def summarize_commands(self) -> list[str]:
        """Get the list of summarize commands."""
        return self._base_ui._summarize_commands

    @property
    def history_manager(self) -> Any:
        """Public read accessor for the conversation history manager."""
        return self._base_ui._history_manager

    @property
    def snapshot_manager(self) -> Any:
        """Public read accessor for the snapshot manager (may be None)."""
        return self._base_ui._snapshot_manager

    @property
    def background_tasks(self) -> Any:
        """Public read accessor for the background-task set."""
        return self._base_ui._background_tasks

    @property
    def confirmation_output_buffer(self) -> list[str]:
        """Public read accessor for the buffered output held during confirmation."""
        return self._base_ui._confirmation_output_buffer

    @property
    def pending_attachments(self) -> list[Any]:
        """Public read accessor for attachments queued for the next turn."""
        return self._base_ui._pending_attachments

    @property
    def plan_mode_active(self) -> bool:
        """Whether plan mode is currently active."""
        return self._base_ui._plan_mode_active

    @plan_mode_active.setter
    def plan_mode_active(self, value: bool):
        self._base_ui._plan_mode_active = value

    @property
    def voice_mode_active(self) -> bool:
        """Whether voice dictation mode is currently active."""
        return self._base_ui._voice_mode_active

    @voice_mode_active.setter
    def voice_mode_active(self, value: bool):
        self._base_ui._voice_mode_active = value

    @property
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""
        return self._base_ui._is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool):
        self._base_ui._is_thinking = value

    @property
    def message_queue(self) -> Any:
        """Public read accessor for the pending-message queue."""
        return self._base_ui._message_queue
