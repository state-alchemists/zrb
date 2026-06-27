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
from zrb.util.cli.style import stylize_muted

if TYPE_CHECKING:
    from typing import Any

    from pydantic_ai.models import Model

    from zrb.llm.task.llm_task import LLMTask


# Ordered modes cycled by Shift+Tab (mirrors Claude Code: normal → auto-accept
# edits → plan → normal). Each maps onto zrb's two orthogonal stores — plan mode
# (the AgentModeState ContextVar) and yolo (xcom) — which the cycle keeps
# mutually exclusive so a single keystroke always lands on a well-defined state.
# Auto-accept-edits reuses selective yolo over the LLM-visible edit-tool names
# (`write_file.__name__ == "Write"`, `replace_in_file.__name__ == "Edit"`), so it
# auto-approves file writes while every other tool still prompts. See ADR-0075.
_AUTO_EDIT_TOOLS = frozenset({"Write", "Edit"})
_MODE_CYCLE = ("normal", "accept_edits", "plan")
_MODE_BANNERS = {
    "normal": "🛠️  NORMAL MODE: tool approvals on",
    "accept_edits": "✏️  AUTO-ACCEPT EDITS: Write/Edit auto-approved, other tools ask",
    "plan": "📋 PLAN MODE: read-only discovery",
}


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
        def yolo(self) -> bool | frozenset: ...

        @yolo.setter
        def yolo(self, value: bool | frozenset) -> None: ...

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
        self.append_to_output(stylize_muted(f"\n  📋 PLAN MODE: {status}\n"))
        self.invalidate_ui()

    def _handle_toggle_plan(self, text: str) -> bool:
        stripped = text.strip()
        for cmd in self._plan_commands:
            if stripped.lower() == cmd.lower():
                self.toggle_plan()
                return True
        return False

    # --- Shift+Tab mode cycle ---------------------------------------------

    def current_cycle_mode(self) -> str:
        """Name of the mode the UI is in, derived from live state.

        Returns a cycle member (``normal`` / ``accept_edits`` / ``plan``), or an
        off-cycle label (``yolo`` / ``custom``) when yolo was set outside the
        Shift+Tab cycle (e.g. ``/yolo`` or ``/yolo Read,Bash`` / Ctrl+Y). Plan
        mode takes precedence so the label never misreports a read-only run.
        """
        if getattr(self, "_plan_mode_active", False):
            return "plan"
        yolo = self.yolo
        if yolo is True:
            return "yolo"
        if isinstance(yolo, frozenset) and yolo:
            return "accept_edits" if yolo == _AUTO_EDIT_TOOLS else "custom"
        return "normal"

    def cycle_mode(self) -> None:
        """Advance to the next Shift+Tab mode and refresh the UI.

        Off-cycle states (full or custom yolo) re-enter the cycle at ``normal``
        so the gesture stays predictable regardless of how yolo was last set.
        """
        current = self.current_cycle_mode()
        if current in _MODE_CYCLE:
            nxt = _MODE_CYCLE[(_MODE_CYCLE.index(current) + 1) % len(_MODE_CYCLE)]
        else:
            nxt = "normal"
        self._apply_cycle_mode(nxt)

    def _apply_cycle_mode(self, name: str) -> None:
        # lazy: circular — permission.state transitively imports zrb.llm.ui,
        # so hoisting this to module level re-enters ui mid-load.
        from zrb.llm.permission.state import AgentMode, set_current_agent_mode

        is_plan = name == "plan"
        self._plan_mode_active = is_plan
        set_current_agent_mode(AgentMode.PLAN if is_plan else AgentMode.BUILD)
        # Cycle states are mutually exclusive: leaving accept-edits (or any
        # other state) clears yolo so plan and auto-approve never stack.
        self.yolo = _AUTO_EDIT_TOOLS if name == "accept_edits" else False
        self.append_to_output(stylize_muted(f"\n  {_MODE_BANNERS[name]}\n"))
        self.invalidate_ui()

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
                        stylize_muted(f"\n  🤖 Small model switched to: {model_name}\n")
                    )
                elif arg.lower().startswith("multimodal "):
                    model_name = arg[11:].strip()
                    if not model_name:
                        continue
                    self._multimodal_model = model_name
                    _llm_config.multimodal_model = model_name
                    self.append_to_output(
                        stylize_muted(
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
                        stylize_muted(f"\n  🤖 Model switched to: {model_name}\n")
                    )
                return True
        return False
