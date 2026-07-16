"""Output rendering for the default `UI`.

Carries the logic for appending text to the read-only output buffer
(`append_to_output`) and rendering the info / status bars. Kept separate
from `default_ui.py` so the prompt-toolkit Application setup stays focused.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, TextIO, cast

from zrb.config.config import CFG
from zrb.llm.agent.activity import agent_activity_registry
from zrb.util.cli.style import stylize_muted
from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from typing import Any

    from prompt_toolkit.formatted_text import AnyFormattedText
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)

# Short labels + styles for the status-bar Shift+Tab mode badge. Keys match
# `ModelCommandsMixin.current_cycle_mode()` (cycle members plus the off-cycle
# yolo/custom states). See ADR-0075.
_MODE_STATUS_LABELS = {
    "normal": "normal",
    "accept_edits": "accept-edits",
    "plan": "plan",
    "yolo": "yolo",
    "custom": "custom-yolo",
}


def _truncate(text: str, limit: int) -> str:
    """First line of `text`, clipped to `limit` chars with an ellipsis."""
    text = text.splitlines()[0] if text else ""
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _fmt_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def _get_mode_status_style(mode: str) -> str:
    """Lazy lookup of the status-bar mode badge style from CFG.

    Module-level dicts would evaluate CFG at import time, baking in the
    values and defeating runtime reconfiguration. This function reads from
    CFG on every call so env-var changes take effect without a restart.
    """
    return {
        "normal": CFG.LLM_UI_STYLE_MODE_NORMAL,
        "accept_edits": CFG.LLM_UI_STYLE_MODE_ACCEPT_EDITS,
        "plan": CFG.LLM_UI_STYLE_MODE_PLAN,
        "yolo": CFG.LLM_UI_STYLE_MODE_YOLO,
        "custom": CFG.LLM_UI_STYLE_MODE_CUSTOM,
    }.get(mode, "")


class OutputMixin:
    """Renders the output field, info bar, and status bar for the default UI."""

    # Host-class contract: state owned by `BaseUI.__init__` and the default
    # `UI.__init__` (prompt-toolkit widgets). Declared here so static type
    # checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        # From BaseUI
        _assistant_name: str
        _conversation_session_name: str
        _current_confirmation: asyncio.Future[str] | None
        _confirmation_output_buffer: list[str]
        _cwd: str
        _git_info: str
        _is_thinking: bool
        _model: "Model | str | None"
        # From default UI (prompt_toolkit widgets — typed as Any to avoid
        # importing heavyweight modules at type-check time).
        _input_field: Any
        _output_field: Any
        # From default UI (`UI.__init__`)
        _pending_invalidate: bool
        _invalidate_task: asyncio.Task | None

        # From BaseUI
        @property
        def yolo(self) -> bool | frozenset: ...

        # From LifecycleMixin
        def invalidate_ui(self) -> None: ...

    @property
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""
        return self._is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool) -> None:
        self._is_thinking = value

    @property
    def current_confirmation(self) -> "asyncio.Future[str] | None":
        """The pending tool-call confirmation future, if any."""
        return self._current_confirmation

    @current_confirmation.setter
    def current_confirmation(self, value: "asyncio.Future[str] | None") -> None:
        self._current_confirmation = value

    @property
    def output_text(self) -> str:
        """Get the current text in the output field."""
        return self._output_field.text

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        # lazy: heavy third-party
        from prompt_toolkit.document import Document

        current_text = self._output_field.text

        # The output window pins itself to the cursor, so follow-the-tail means
        # "keep the cursor on the last line". While it is, new chunks scroll
        # into view; the moment the user scrolls up (which moves the cursor up —
        # see create_output_field's mouse handler / the output keybindings) the
        # cursor leaves the last line and we freeze, preserving their position.
        # Scrolling back down to the last line resumes following. Works
        # regardless of which pane is focused, so the thinking process can be
        # read mid-stream without first focusing the output pane (Ctrl+K).
        is_at_last_line = True
        try:
            doc = self._output_field.buffer.document
            is_at_last_line = doc.cursor_position_row >= doc.line_count - 1
        except Exception:
            pass
        should_scroll_to_end = is_at_last_line

        content = sep.join([str(value) for value in values]) + end

        # Buffer main-agent output while a confirmation is pending during
        # streaming, so the confirmation prompt is not interleaved with tokens.
        if self._current_confirmation is not None and self._is_thinking:
            self._confirmation_output_buffer.append(content)
            self._schedule_invalidate()
            return

        if kind not in ("text", "todo_progress"):

            content = stylize_muted(content)

        # Handle carriage returns (\r) for status updates
        if "\r" in content:
            last_newline = current_text.rfind("\n")
            if last_newline == -1:
                previous = ""
                last = current_text
            else:
                previous = current_text[: last_newline + 1]
                last = current_text[last_newline + 1 :]
            combined = last + content
            resolved = re.sub(r"[^\n]*\r", "", combined)
            new_text = previous + resolved
        else:
            new_text = current_text + content

        # NB: we deliberately do NOT fire a Notification hook per output chunk.
        # The Claude-Code `Notification` event means "the agent needs your
        # attention" (permission/idle), not "output was produced"; firing it per
        # streamed chunk spawned a command-hook subprocess per chunk, which under
        # a real hook like peon-ping exhausted file descriptors and timed out.
        # Genuine attention notifications fire at the right moments instead
        # (PermissionRequest on approval; elicitation_dialog on AskUserQuestion).

        new_cursor_position = (
            len(new_text)
            if should_scroll_to_end
            else self._output_field.buffer.cursor_position
        )
        new_cursor_position = min(max(0, new_cursor_position), len(new_text))

        self._output_field.buffer.set_document(
            Document(new_text, cursor_position=new_cursor_position),
            bypass_readonly=True,
        )
        self._schedule_invalidate()

    def _schedule_invalidate(self):
        if self._pending_invalidate:
            return
        self._pending_invalidate = True

        async def _do_invalidate():
            await asyncio.sleep(0.016)
            self._pending_invalidate = False
            self.invalidate_ui()

        try:
            self._invalidate_task = asyncio.create_task(_do_invalidate())
        except RuntimeError:
            self._pending_invalidate = False
            self.invalidate_ui()

    @property
    def output_field_width(self) -> int | None:
        """Get the output field width."""
        try:
            width = get_terminal_size().columns - 4
            if width < 10:
                width = None
        except Exception:
            width = None
        return width

    def get_info_bar_text(self) -> "AnyFormattedText":
        # lazy: heavy third-party
        from prompt_toolkit.formatted_text.utils import fragment_list_width

        model_name = "Unknown"
        if self._model:
            if isinstance(self._model, str):
                model_name = self._model
            elif hasattr(self._model, "model_name"):
                model_name = getattr(self._model, "model_name")
            else:
                model_name = str(self._model)

        # Build the bar as (style, text) fragments rather than HTML. This lets the
        # INFO_* knobs hold full prompt_toolkit style strings (e.g. "ansired bold"),
        # consistent with every other LLM_UI_STYLE_* field, and avoids embedding
        # runtime strings (model/cwd/git) into HTML where '<'/'&' would break markup.
        def _bold(style: str) -> str:
            return f"{style} bold" if style else "bold"

        _yolo = self.yolo
        if _yolo is True:
            yolo_frag = (_bold(CFG.LLM_UI_STYLE_INFO_YOLO_ON), "ON ")
        elif isinstance(_yolo, frozenset) and _yolo:
            tools_str = ",".join(sorted(_yolo))
            yolo_frag = (_bold(CFG.LLM_UI_STYLE_INFO_YOLO_PARTIAL), f"[{tools_str}]")
        else:
            yolo_frag = (CFG.LLM_UI_STYLE_INFO_YOLO_OFF, "OFF")

        if getattr(self, "_plan_mode_active", False):
            plan_frag = (_bold(CFG.LLM_UI_STYLE_INFO_PLAN_ON), "On ")
        else:
            plan_frag = (CFG.LLM_UI_STYLE_INFO_PLAN_OFF, "Off")

        line1 = [
            ("", " 🤖 "),
            ("bold", "Model:"),
            ("", f" {model_name} | 💬 "),
            ("bold", "Session:"),
            ("", f" {self._conversation_session_name} "),
        ]
        line2 = [
            ("", " 📋 "),
            ("bold", "Plan Mode:"),
            ("", " "),
            plan_frag,
            ("", " | 🤠 "),
            ("bold", "YOLO:"),
            ("", " "),
            yolo_frag,
            ("", " "),
        ]
        line3 = [
            ("", " 📂 "),
            ("bold", "Dir:"),
            ("", f" {self._cwd} | 🌿 "),
            ("bold", "Git:"),
            ("", f" {self._git_info} "),
        ]

        total_cols = get_terminal_size().columns

        def center_line(fragments: list) -> list:
            visible_width = fragment_list_width(fragments)
            padding = max(0, (total_cols - visible_width) // 2)
            trailing = max(0, total_cols - visible_width - padding)
            return [("", " " * padding), *fragments, ("", " " * trailing)]

        return [
            *center_line(line1),
            ("", "\n"),
            *center_line(line2),
            ("", "\n"),
            *center_line(line3),
        ]

    def get_agent_activity_text(self) -> "AnyFormattedText":
        """One line per running sub-agent: #ordinal name · task — activity.

        This panel is the legend for the [name #ordinal] prefixes in the output
        stream. Empty when nothing is delegating, so it collapses to zero height.
        Refreshed by the app's periodic redraw (LLM_UI_REFRESH_INTERVAL).
        """
        agents = agent_activity_registry.active()
        if not agents:
            return []
        frags: list = []
        for agent in agents:
            label = f" 🔧 #{agent.ordinal} {agent.name}"
            if agent.task:
                label += f" · {_truncate(agent.task, 50)}"
            if agent.last_line:
                label += f" — {_truncate(agent.last_line, 40)}"
            frags.append((CFG.LLM_UI_STYLE_THINKING, label))
            frags.append(("", "\n"))
        return frags[:-1]  # drop trailing newline so height == agent count

    def get_status_bar_text(self) -> "AnyFormattedText":
        if self.current_confirmation is not None:
            dots = getattr(self, "_confirmation_dots", 0)
            next_dots = (dots + 1) % 4
            setattr(self, "_confirmation_dots", next_dots)
            dot_str = "." * next_dots + " " * (3 - next_dots)
            return [
                (
                    CFG.LLM_UI_STYLE_CONFIRMATION,
                    f" 👋 {self._assistant_name} is waiting for confirmation{dot_str} ",
                )
            ]
        if self.is_thinking:
            dots = getattr(self, "_thinking_dots", 0)
            next_dots = (dots + 1) % 4
            setattr(self, "_thinking_dots", next_dots)
            dot_str = "." * next_dots + " " * (3 - next_dots)
            return [
                (
                    CFG.LLM_UI_STYLE_THINKING,
                    f" ⏳ {self._assistant_name} is working{dot_str} ",
                ),
                *self._get_token_usage_fragments(),
            ]
        # Persistent Shift+Tab mode indicator (mirrors Claude Code's mode badge
        # near the prompt). `current_cycle_mode` lives on ModelCommandsMixin;
        # guard for lightweight UIs/mocks that don't compose it. See ADR-0075.
        get_mode = getattr(self, "current_cycle_mode", None)
        mode = cast(str, get_mode()) if callable(get_mode) else "normal"
        result: list = [
            (CFG.LLM_UI_STYLE_STATUS, " 🚀 Ready "),
            (
                _get_mode_status_style(mode),
                f" {_MODE_STATUS_LABELS.get(mode, mode)} ",
            ),
            (f"fg:{CFG.LLM_UI_STYLE_FAINT}", "shift+tab to cycle "),
        ]
        # Voice mode indicator (see ADR-0081)
        if getattr(self, "_voice_mode_active", False):
            result.append((CFG.LLM_UI_STYLE_STATUS, " 🎤 VOICE "))
        result.extend(self._get_token_usage_fragments())
        return result

    def _get_token_usage_fragments(self) -> list:
        """Session token totals as status-bar fragments; empty until first run."""
        input_tokens, output_tokens = cast(
            tuple[int, int], getattr(self, "session_token_usage", (0, 0))
        )
        if not input_tokens and not output_tokens:
            return []
        text = f" 💸 {_fmt_tokens(input_tokens)} in · {_fmt_tokens(output_tokens)} out"
        cached = cast(int, getattr(self, "session_cache_read_tokens", 0))
        if cached:
            text += f" · {_fmt_tokens(cached)} cached"
        context = cast(int, getattr(self, "context_tokens", 0))
        if context:
            text += f" · 🧠 {_fmt_tokens(context)} ctx"
        return [(f"fg:{CFG.LLM_UI_STYLE_FAINT}", text + " ")]
