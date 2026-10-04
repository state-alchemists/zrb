"""Model / mode slash-commands for `BaseUI`.

YOLO toggle, PLAN-mode toggle, and model switching (`/model`, including the
`small`/`multimodal` variants). Composed into `BaseUICommands` as
`self._models`.

Each `handle_*` returns ``True`` if the input was consumed, ``False``
otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.permission.state import AgentMode, set_current_agent_mode
from zrb.llm.ui.ui_config import command_alias_field, model_visibility_field
from zrb.util.cli.style import stylize_error, stylize_muted, stylize_warning

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI
    from zrb.llm.ui.ui_config import UIConfig

# `/set` names that switch the UI's live model slots, exactly as `/model` does.
_LIVE_MODEL_SLOTS = frozenset({"model", "small_model", "multimodal_model"})

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
    "normal": "🔧 NORMAL MODE: tool approvals on",
    "accept_edits": "📝 AUTO-ACCEPT EDITS: Write/Edit auto-approved, other tools ask",
    "plan": "📋 PLAN MODE: read-only discovery",
}


class BaseUIModelCommands:
    """YOLO / PLAN / model-switch slash commands for BaseUI."""

    def __init__(self, base_ui: "BaseUI") -> None:
        self._base_ui = base_ui

    # --- yolo / model -----------------------------------------------------

    def toggle_yolo(self):
        """Toggle YOLO mode (full on/off) and force refresh."""
        self._base_ui.yolo = not bool(self._base_ui.yolo)
        self._base_ui.invalidate_ui()

    def handle_toggle_yolo(self, text: str) -> bool:
        stripped = text.strip()
        for cmd in self._base_ui.yolo_toggle_commands:
            if stripped.lower() == cmd.lower():
                self.toggle_yolo()
                return True
            if stripped.lower().startswith(cmd.lower() + " "):
                # /yolo Write,Edit — activate selective yolo for those tools
                tools_str = stripped[len(cmd) :].strip()
                tools = frozenset(t.strip() for t in tools_str.split(",") if t.strip())
                if tools:
                    self._base_ui.yolo = tools
                    self._base_ui.invalidate_ui()
                return True
        return False

    def toggle_plan(self):
        """Toggle plan mode on/off and force refresh."""
        self._base_ui.plan_mode_active = not self._base_ui.plan_mode_active
        set_current_agent_mode(
            AgentMode.PLAN if self._base_ui.plan_mode_active else AgentMode.BUILD
        )
        status = "On" if self._base_ui.plan_mode_active else "Off"
        self._base_ui.append_to_output(stylize_muted(f"\n  📋 PLAN MODE: {status}\n"))
        self._base_ui.invalidate_ui()

    def handle_toggle_plan(self, text: str) -> bool:
        stripped = text.strip()
        for cmd in self._base_ui.plan_commands:
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
        if self._base_ui.plan_mode_active:
            return "plan"
        yolo = self._base_ui.yolo
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
        self._base_ui.plan_mode_active = is_plan
        set_current_agent_mode(AgentMode.PLAN if is_plan else AgentMode.BUILD)
        # Cycle states are mutually exclusive: leaving accept-edits (or any
        # other state) clears yolo so plan and auto-approve never stack.
        self._base_ui.yolo = _AUTO_EDIT_TOOLS if name == "accept_edits" else False
        self._base_ui.append_to_output(stylize_muted(f"\n  {_MODE_BANNERS[name]}\n"))
        self._base_ui.invalidate_ui()

    def handle_set_model_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._base_ui.set_model_commands:
            prefix = f"{cmd} "
            # `classify_input` matched case-insensitively, so an alias like
            # `/MODEL` reaches here; lowercasing the prefix keeps the two in
            # lockstep (otherwise the token is recognized but never handled).
            if text.lower().startswith(prefix.lower()):
                if self._base_ui.is_thinking:
                    return False
                arg = text[len(prefix) :].strip()
                if not arg:
                    continue

                if arg.lower().startswith("small "):
                    model_name = arg[6:].strip()
                    if not model_name:
                        continue
                    self._set_live_model("small_model", model_name)
                elif arg.lower().startswith("multimodal "):
                    model_name = arg[11:].strip()
                    if not model_name:
                        continue
                    self._set_live_model("multimodal_model", model_name)
                else:
                    self._set_live_model("model", arg)
                return True
        return False

    def _set_live_model(self, slot: str, model_name: str) -> None:
        """Apply a model switch to one of the UI's live model slots.

        Mirrors the three branches of `/model` so `/set` can drive the same
        live switch. `slot` is one of `model`, `small_model`,
        `multimodal_model`.
        """
        if slot == "small_model":
            # Bound by run_agent as `current_small_model`.
            self._base_ui.small_model = model_name
            label = "Small model"
        elif slot == "multimodal_model":
            # Bound by run_agent as `current_multimodal_model`.
            self._base_ui.multimodal_model = model_name
            label = "Multimodal model"
        else:
            self._base_ui.model = model_name
            try:
                self._base_ui.llm_task.prompt_manager.model = model_name
            except Exception as e:
                CFG.LOGGER.debug(f"Failed to set prompt-manager model: {e}")
            label = "Model"
        self._base_ui.append_to_output(
            stylize_muted(f"\n  🤖 {label} switched to: {model_name}\n")
        )

    def handle_set_command(self, text: str):
        text = text.strip()
        for cmd in self._base_ui.set_commands:
            if text.lower() == cmd.lower():
                # Bare `/set` follows the same thinking guard as
                # `/set NAME VALUE`.
                if self._base_ui.is_thinking:
                    return False
                self._base_ui.append_to_output(
                    stylize_warning(
                        f"\n  ❗ Setting name and value required — usage: "
                        f"{cmd} <name> <value>\n"
                    )
                )
                return True
            prefix = f"{cmd} "
            if not text.lower().startswith(prefix.lower()):
                continue
            if self._base_ui.is_thinking:
                return False
            rest = text[len(prefix) :].strip()
            parts = rest.split(None, 1)
            if not parts:
                self._base_ui.append_to_output(
                    stylize_warning(
                        f"\n  ❗ Setting name and value required — usage: "
                        f"{cmd} <name> <value>\n"
                    )
                )
                return True
            name = parts[0]
            value = parts[1].strip() if len(parts) > 1 else ""
            if not value:
                self._base_ui.append_to_output(
                    stylize_warning(
                        f"\n  ❗ Value required for {name!r} — usage: "
                        f"{cmd} {name} <value>\n"
                    )
                )
                return True
            slot = name.lower()
            if slot in _LIVE_MODEL_SLOTS:
                self._set_live_model(slot, value)
                return True
            self._set_cfg_setting(name.upper(), value)
            return True
        return False

    def _refresh_live_session(self, name: str, value: object) -> None:
        """Apply a changed startup-snapshotted setting to the running session.

        `UIConfig` copies the `LLM_UI_COMMAND_*` alias lists and the two
        model-visibility flags when the session is built, and the completer
        copies them again, so both copies are re-pointed here.
        """
        ui_config = self._base_ui.ui_config
        visibility_field = model_visibility_field(name)
        if visibility_field is not None:
            setattr(ui_config, visibility_field, bool(value))
            self._refresh_completer("refresh_model_visibility", ui_config)
            return
        alias_field = command_alias_field(name)
        if alias_field is None:
            return
        # `convert_setting_value` is typed `-> object` because most settings are
        # scalars; a `LLM_UI_COMMAND_*` alias is always a list, so narrow rather
        # than trust the annotation.
        if not isinstance(value, list):
            return
        setattr(ui_config, alias_field, list(value))
        self._refresh_completer("refresh_command_aliases", ui_config)

    def _refresh_completer(self, method_name: str, ui_config: "UIConfig") -> None:
        """Call `method_name` on the running input completer, when it has one.

        The completer is reached through the input field rather than held, and
        another UI's completer may not implement the refresh hook at all, so the
        capability probe keeps that a no-op instead of an error.
        """
        completer = getattr(
            getattr(self._base_ui, "input_field", None), "completer", None
        )
        refresh = getattr(completer, method_name, None)
        if refresh is not None:
            refresh(ui_config)

    def _set_cfg_setting(self, name: str, value: str) -> None:
        """Assign `CFG.<name>` from a raw string, echoing a confirmation.

        Unknown names and uncastable values raise before any write; both are
        rendered as friendly errors (R1/R2/R10) rather than propagated.
        """
        field = CFG.get_settable_field(name)
        try:
            converted = CFG.convert_setting_value(name, value)
        except AttributeError as error:
            self._base_ui.append_to_output(stylize_error(f"\n  ❌ {error}\n"))
            return
        except ValueError as error:
            self._base_ui.append_to_output(stylize_error(f"\n  ❌ {error}\n"))
            return
        setattr(CFG, name, converted)
        self._refresh_live_session(name, converted)
        shown = "[set]" if field is not None and field.secret else repr(converted)
        self._base_ui.append_to_output(stylize_muted(f"\n  🔧 Set {name} = {shown}\n"))
        self._base_ui.invalidate_ui()
