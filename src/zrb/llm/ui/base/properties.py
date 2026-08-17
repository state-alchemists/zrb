"""Pure attribute-accessor properties for `BaseUI`.

Extracted from `base/ui.py` to keep that class focused on behavior. Every
property here is a thin getter/setter over a `self._<attr>` slot set in
`BaseUI.__init__`; none carries logic or side effects (those stay in
`base/ui.py`). Composed into `BaseUI` via MRO, so callers keep reading the
same public names (e.g. `ui.exit_commands`).
"""

from collections.abc import AsyncIterable, Callable
from typing import TYPE_CHECKING, Any

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand


class BaseUIProperties:
    """Pure attribute accessors for BaseUI (no logic, no side effects)."""

    if TYPE_CHECKING:
        # Backing state owned by `BaseUI.__init__`; declared so static type
        # checkers can verify the accesses below. Does not run at runtime.
        _llm_task: Any
        _model: Any
        _small_model: Any
        _multimodal_model: Any
        _conversation_session_name: str
        _triggers: list[Callable[[], AsyncIterable[Any]]]
        _last_result_data: str | None
        _assistant_name: str
        _initial_message: Any
        _exit_commands: list[str]
        _info_commands: list[str]
        _save_commands: list[str]
        _load_commands: list[str]
        _attach_commands: list[str]
        _photo_commands: list[str]
        _redirect_output_commands: list[str]
        _yolo_toggle_commands: list[str]
        _set_model_commands: list[str]
        _exec_commands: list[str]
        _custom_commands: list["AnyCustomCommand"]
        _summarize_commands: list[str]
        _history_manager: Any
        _snapshot_manager: Any
        _background_tasks: Any
        _confirmation_output_buffer: list[str]
        _pending_attachments: list[Any]
        _plan_mode_active: bool
        _voice_mode_active: bool
        _is_thinking: bool
        _message_queue: Any

    @property
    def llm_task(self) -> Any:
        """Get the LLM task."""
        return self._llm_task

    @llm_task.setter
    def llm_task(self, value: Any):
        """Set the LLM task."""
        self._llm_task = value

    @property
    def model(self) -> Any:
        """Get the current model."""
        return self._model

    @model.setter
    def model(self, value: Any):
        """Set the model."""
        self._model = value

    @property
    def small_model(self) -> Any:
        """Get the current small model."""
        return self._small_model

    @small_model.setter
    def small_model(self, value: Any):
        """Set the small model."""
        self._small_model = value

    @property
    def multimodal_model(self) -> Any:
        """Get the current multimodal model."""
        return self._multimodal_model

    @multimodal_model.setter
    def multimodal_model(self, value: Any):
        """Set the multimodal model."""
        self._multimodal_model = value

    @property
    def conversation_session_name(self) -> str:
        """Get the conversation session name."""
        return self._conversation_session_name

    @conversation_session_name.setter
    def conversation_session_name(self, value: str):
        """Set the conversation session name."""
        self._conversation_session_name = value

    @property
    def triggers(self) -> list[Callable[[], AsyncIterable[Any]]]:
        return self._triggers

    @triggers.setter
    def triggers(self, value: list[Callable[[], AsyncIterable[Any]]]):
        self._triggers = value

    @property
    def last_output(self) -> str:
        if self._last_result_data is None:
            return ""
        return self._last_result_data

    @property
    def assistant_name(self) -> str:
        """Get the assistant name."""
        return self._assistant_name

    @property
    def initial_message(self) -> Any:
        """Get the initial message."""
        return self._initial_message

    @property
    def exit_commands(self) -> list[str]:
        """Get the list of exit commands."""
        return self._exit_commands

    @property
    def info_commands(self) -> list[str]:
        """Get the list of info/help commands."""
        return self._info_commands

    @property
    def save_commands(self) -> list[str]:
        """Get the list of save commands."""
        return self._save_commands

    @property
    def load_commands(self) -> list[str]:
        """Get the list of load commands."""
        return self._load_commands

    @property
    def attach_commands(self) -> list[str]:
        """Get the list of attach commands."""
        return self._attach_commands

    @property
    def photo_commands(self) -> list[str]:
        """Get the list of photo capture commands."""
        return self._photo_commands

    @property
    def redirect_output_commands(self) -> list[str]:
        """Get the list of redirect output commands."""
        return self._redirect_output_commands

    @property
    def yolo_toggle_commands(self) -> list[str]:
        """Get the list of yolo toggle commands."""
        return self._yolo_toggle_commands

    @property
    def set_model_commands(self) -> list[str]:
        """Get the list of set model commands."""
        return self._set_model_commands

    @property
    def exec_commands(self) -> list[str]:
        """Get the list of exec commands."""
        return self._exec_commands

    @property
    def custom_commands(self) -> list[AnyCustomCommand]:
        """Get the list of custom commands."""
        return self._custom_commands

    @property
    def summarize_commands(self) -> list[str]:
        """Get the list of summarize commands."""
        return self._summarize_commands

    @property
    def history_manager(self) -> Any:
        """Public read accessor for the conversation history manager."""
        return self._history_manager

    @property
    def snapshot_manager(self) -> Any:
        """Public read accessor for the snapshot manager (may be None)."""
        return self._snapshot_manager

    @property
    def background_tasks(self) -> Any:
        """Public read accessor for the background-task set."""
        return self._background_tasks

    @property
    def confirmation_output_buffer(self) -> list[str]:
        """Public read accessor for the buffered output held during confirmation."""
        return self._confirmation_output_buffer

    @property
    def pending_attachments(self) -> list[Any]:
        """Public read accessor for attachments queued for the next turn."""
        return self._pending_attachments

    @property
    def plan_mode_active(self) -> bool:
        """Whether plan mode is currently active."""
        return self._plan_mode_active

    @plan_mode_active.setter
    def plan_mode_active(self, value: bool):
        self._plan_mode_active = value

    @property
    def voice_mode_active(self) -> bool:
        """Whether voice dictation mode is currently active."""
        return self._voice_mode_active

    @voice_mode_active.setter
    def voice_mode_active(self, value: bool):
        self._voice_mode_active = value

    @property
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""
        return self._is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool):
        self._is_thinking = value

    @property
    def message_queue(self) -> Any:
        """Public read accessor for the pending-message queue."""
        return self._message_queue
