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


class PropertiesMixin:
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
