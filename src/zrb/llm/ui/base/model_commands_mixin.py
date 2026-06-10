"""Model / mode slash-commands for `BaseUI`.

YOLO toggle, PLAN-mode toggle, and model switching (`/model`, including the
`small`/`multimodal` variants). Split out of `commands_mixin.py`; the handlers
run on the composed `BaseUI` instance (see the host-class contract below),
mirroring `CommandsMixin`.

Each `_handle_*` returns ``True`` if the input was consumed, ``False``
otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.config.config import llm_config as _llm_config
from zrb.util.cli.style import stylize_faint

if TYPE_CHECKING:
    from typing import Any

    from pydantic_ai.models import Model

    from zrb.llm.task.llm_task import LLMTask


class ModelCommandsMixin:
    """YOLO / PLAN / model-switch slash commands for BaseUI."""

    # Host-class contract: state and methods owned by `BaseUI`. Declared here
    # so type checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        _plan_commands: list[str]
        _plan_mode_active: bool
        _set_model_commands: list[str]
        _yolo_toggle_commands: list[str]
        _is_thinking: bool
        _llm_task: "LLMTask"
        _model: "Model | str | None"
        _small_model: "Model | str | None"
        _multimodal_model: "Model | str | None"

        @property
        def yolo(self) -> bool: ...

        @yolo.setter
        def yolo(self, value: Any) -> None: ...

        def append_to_output(self, *values: Any, **kwargs: Any) -> None: ...

        def invalidate_ui(self) -> None: ...

    # --- yolo / model -----------------------------------------------------

    def toggle_yolo(self):
        """Toggle YOLO mode (full on/off) and force refresh."""
        self.yolo = not bool(self.yolo)
        self.invalidate_ui()

    def _handle_toggle_yolo(self, text: str) -> bool:
        stripped = text.strip()
        for cmd in self._yolo_toggle_commands:
            if stripped.lower() == cmd.lower():
                # Plain /yolo — toggle full yolo on/off
                self.toggle_yolo()
                return True
            if stripped.lower().startswith(cmd.lower() + " "):
                # /yolo Write,Edit — activate selective yolo for those tools
                tools_str = stripped[len(cmd) :].strip()
                tools = frozenset(t.strip() for t in tools_str.split(",") if t.strip())
                if tools:
                    self.yolo = tools
                    self.invalidate_ui()
                return True
        return False

    def toggle_plan(self):
        """Toggle plan mode on/off and force refresh."""
        self._plan_mode_active = not self._plan_mode_active
        # lazy: circular — permission.state transitively imports zrb.llm.ui,
        # so hoisting this to module level re-enters ui mid-load.
        from zrb.llm.permission.state import (
            AgentMode,
            set_current_agent_mode,
        )

        set_current_agent_mode(
            AgentMode.PLAN if self._plan_mode_active else AgentMode.BUILD
        )
        status = "On" if self._plan_mode_active else "Off"
        self.append_to_output(stylize_faint(f"\n  📋 PLAN MODE: {status}\n"))
        self.invalidate_ui()

    def _handle_toggle_plan(self, text: str) -> bool:
        stripped = text.strip()
        for cmd in self._plan_commands:
            if stripped.lower() == cmd.lower():
                self.toggle_plan()
                return True
        return False

    def _handle_set_model_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._set_model_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                if self._is_thinking:
                    return False
                arg = text[len(prefix) :].strip()
                if not arg:
                    continue

                if arg.lower().startswith("small "):
                    model_name = arg[6:].strip()
                    if not model_name:
                        continue
                    self._small_model = model_name
                    _llm_config.small_model = model_name
                    self.append_to_output(
                        stylize_faint(f"\n  🤖 Small model switched to: {model_name}\n")
                    )
                elif arg.lower().startswith("multimodal "):
                    model_name = arg[11:].strip()
                    if not model_name:
                        continue
                    self._multimodal_model = model_name
                    _llm_config.multimodal_model = model_name
                    self.append_to_output(
                        stylize_faint(
                            f"\n  🤖 Multimodal model switched to: {model_name}\n"
                        )
                    )
                else:
                    # Main model — existing behavior unchanged
                    model_name = arg
                    self._model = model_name
                    try:
                        self._llm_task.prompt_manager.model = model_name
                    except Exception:
                        pass
                    self.append_to_output(
                        stylize_faint(f"\n  🤖 Model switched to: {model_name}\n")
                    )
                return True
        return False
