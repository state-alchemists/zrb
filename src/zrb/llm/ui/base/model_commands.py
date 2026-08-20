"""Model / mode slash-commands for `BaseUI`.

YOLO toggle, PLAN-mode toggle, and model switching (`/model`, including the
`small`/`multimodal` variants). Split out of `commands.py`. Composed into
`BaseUICommands` as `self._model`, taking the owning `BaseUI` and
reading/calling its state/methods through that reference.

Each `_handle_*` returns ``True`` if the input was consumed, ``False``
otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.config import llm_config as _llm_config
from zrb.llm.permission.state import AgentMode, set_current_agent_mode
from zrb.util.cli.style import stylize_muted

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI

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


class BaseUIModelCommands:
    """YOLO / PLAN / model-switch slash commands for BaseUI."""

    def __init__(self, owner: "BaseUI") -> None:
        self._owner = owner

    # --- yolo / model -----------------------------------------------------

    def toggle_yolo(self):
        """Toggle YOLO mode (full on/off) and force refresh."""
        self._owner.yolo = not bool(self._owner.yolo)
        self._owner.invalidate_ui()

    def _handle_toggle_yolo(self, text: str) -> bool:
        stripped = text.strip()
        for cmd in self._owner._yolo_toggle_commands:
            if stripped.lower() == cmd.lower():
                # Plain /yolo — toggle full yolo on/off
                self.toggle_yolo()
                return True
            if stripped.lower().startswith(cmd.lower() + " "):
                # /yolo Write,Edit — activate selective yolo for those tools
                tools_str = stripped[len(cmd) :].strip()
                tools = frozenset(t.strip() for t in tools_str.split(",") if t.strip())
                if tools:
                    self._owner.yolo = tools
                    self._owner.invalidate_ui()
                return True
        return False

    def toggle_plan(self):
        """Toggle plan mode on/off and force refresh."""
        self._owner._plan_mode_active = not self._owner._plan_mode_active
        set_current_agent_mode(
            AgentMode.PLAN if self._owner._plan_mode_active else AgentMode.BUILD
        )
        status = "On" if self._owner._plan_mode_active else "Off"
        self._owner.append_to_output(stylize_muted(f"\n  📋 PLAN MODE: {status}\n"))
        self._owner.invalidate_ui()

    def _handle_toggle_plan(self, text: str) -> bool:
        stripped = text.strip()
        for cmd in self._owner._plan_commands:
            if stripped.lower() == cmd.lower():
                self.toggle_plan()
                return True
        return False

    # --- Shift+Tab mode cycle ---------------------------------------------

    def current_cycle_mode(self) -> str:
        """Name of the mode the UI is in, derived from live state.

        Returns a cycle member (``normal`` / ``accept_edits`` / ``plan``), or an
        off-cycle label (``yolo`` / ``custom``) when yolo was set outside the
        Shift+Tab cycle (e.g. ``/yolo`` or ``/yolo Read,Shell`` / Ctrl+Y). Plan
        mode takes precedence so the label never misreports a read-only run.
        """
        if getattr(self._owner, "_plan_mode_active", False):
            return "plan"
        yolo = self._owner.yolo
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
        is_plan = name == "plan"
        self._owner._plan_mode_active = is_plan
        set_current_agent_mode(AgentMode.PLAN if is_plan else AgentMode.BUILD)
        # Cycle states are mutually exclusive: leaving accept-edits (or any
        # other state) clears yolo so plan and auto-approve never stack.
        self._owner.yolo = _AUTO_EDIT_TOOLS if name == "accept_edits" else False
        self._owner.append_to_output(stylize_muted(f"\n  {_MODE_BANNERS[name]}\n"))
        self._owner.invalidate_ui()

    def _handle_set_model_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._owner._set_model_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                if self._owner._is_thinking:
                    return False
                arg = text[len(prefix) :].strip()
                if not arg:
                    continue

                if arg.lower().startswith("small "):
                    model_name = arg[6:].strip()
                    if not model_name:
                        continue
                    self._owner._small_model = model_name
                    _llm_config.small_model = model_name
                    self._owner.append_to_output(
                        stylize_muted(f"\n  🤖 Small model switched to: {model_name}\n")
                    )
                elif arg.lower().startswith("multimodal "):
                    model_name = arg[11:].strip()
                    if not model_name:
                        continue
                    self._owner._multimodal_model = model_name
                    _llm_config.multimodal_model = model_name
                    self._owner.append_to_output(
                        stylize_muted(
                            f"\n  🤖 Multimodal model switched to: {model_name}\n"
                        )
                    )
                else:
                    # Main model — existing behavior unchanged
                    model_name = arg
                    self._owner._model = model_name
                    try:
                        self._owner._llm_task.prompt_manager.model = model_name
                    except Exception as e:
                        CFG.LOGGER.debug(f"Failed to set prompt-manager model: {e}")
                    self._owner.append_to_output(
                        stylize_muted(f"\n  🤖 Model switched to: {model_name}\n")
                    )
                return True
        return False
