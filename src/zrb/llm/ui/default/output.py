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
from zrb.util.truncate import truncate_display
from zrb.llm.agent.activity import agent_activity_registry
from zrb.util.cli.help_panel import render_help_panel
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_muted
from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from prompt_toolkit.formatted_text import AnyFormattedText
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)

# Short labels + styles for the status-bar Shift+Tab mode badge. Keys match
# `BaseUIModelCommands.current_cycle_mode()` (cycle members plus the off-cycle
# yolo/custom states). See ADR-0073.
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
    return truncate_display(text, limit)


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


class UIOutput:
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
        _rendered_blocks: list[list]
        _rendered_width: int | None
        _markdown_theme: Any
        _application: Any

        # From BaseUI. The setter is declared too: BaseUI.yolo has one, and a
        # getter-only stub here reads as a narrowing override on the composed
        # `UI` class (reportIncompatibleMethodOverride).
        @property
        def yolo(self) -> bool | frozenset: ...

        @yolo.setter
        def yolo(self, value: bool | frozenset) -> None: ...

        # From UILifecycle
        def invalidate_ui(self) -> None: ...

        # From BaseUICommands
        def get_help_panel(
            self, art: str = "", header: str = "", max_commands: int | None = None
        ) -> Any: ...

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
        #
        # "Cursor on the last line" == "no newline after the cursor". Checked on
        # the raw string on purpose: document.cursor_position_row/line_count
        # build the Document's line index — an O(buffer) scan on EVERY streamed
        # chunk (the render path rebuilds it anyway, but only at the debounced
        # ~60Hz rate, not per token). str.find early-exits, so this is O(1)
        # while following and O(distance to next newline) when scrolled up.
        is_at_last_line = True
        try:
            cursor = self._output_field.buffer.cursor_position
            is_at_last_line = current_text.find("\n", cursor) == -1
        except Exception:
            # Per-chunk render hot path; default to "at last line" if the
            # buffer isn't queryable rather than logging on every token.
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

    def append_markdown(self, markdown_text: str) -> None:
        """Append rendered markdown, remembering the source (public API)."""
        self.append_rendered(markdown_text, self._render_markdown_block)

    def print_help(self) -> None:
        """Append the help panel as a re-renderable block (public API).

        Overrides `BaseUICommands.print_help` so `/help` re-lays out on resize
        the same way the greeting panel does.
        """
        self.append_rendered(self.get_help_panel(), render_help_panel)

    def append_rendered(
        self, source: Any, renderer: "Callable[[Any, int | None], str]"
    ) -> None:
        """Append width-dependent output, remembering how to re-render it.

        Rich hard-wraps at render time, so a resized terminal would keep the old
        line breaks forever. Recording (start, end, source, renderer) lets
        `rewrap_output` splice a fresh render in at the new width. The trailing
        newline is appended separately so it stays outside the span.
        """
        rendered = renderer(source, self.output_field_width)
        start = len(self.output_text)
        self.append_to_output(rendered, end="")
        end = len(self.output_text)
        self.append_to_output("")
        # Only track what landed verbatim — a pending confirmation buffers the
        # content instead of inserting it, which would make the span a lie.
        if end - start == len(rendered):
            self._rendered_blocks.append([start, end, source, renderer])

    def rewrap_output(self) -> None:
        """Re-render tracked blocks at the current width (public API).

        Called from the app's after-render hook; a no-op unless the terminal
        width actually changed.
        """
        width = self.output_field_width
        if width == self._rendered_width:
            return
        self._rendered_width = width
        if not self._rendered_blocks:
            return
        # ponytail: splices by recorded offsets, which assumes nothing rewrote
        # the transcript inside a tracked span (only the trailing status line
        # is ever rewritten, via \r). If that stops holding, store the rendered
        # text per block and rebuild the whole buffer from the block list.
        text = self.output_text
        shift = 0
        for block in self._rendered_blocks:
            start, end = block[0] + shift, block[1] + shift
            rendered = block[3](block[2], width)
            text = text[:start] + rendered + text[end:]
            block[0], block[1] = start, start + len(rendered)
            shift += len(rendered) - (end - start)
        self._set_output_text(text)

    def _render_markdown_block(self, markdown_text: str, width: int | None) -> str:
        return render_markdown(markdown_text, width=width, theme=self._markdown_theme)

    def _set_output_text(self, text: str) -> None:
        # lazy: heavy third-party
        from prompt_toolkit.document import Document

        buffer = self._output_field.buffer
        follows_tail = buffer.cursor_position >= len(buffer.text)
        cursor = len(text) if follows_tail else min(buffer.cursor_position, len(text))
        buffer.set_document(
            Document(text, cursor_position=cursor), bypass_readonly=True
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
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._pending_invalidate = False
            self.invalidate_ui()
            return
        self._invalidate_task = loop.create_task(_do_invalidate())

    @property
    def output_field_width(self) -> int | None:
        """Get the output field width.

        Asks the running application first: its output is a dup of the real
        stdout, while `get_terminal_size` has to probe fds 1/2 that
        `GlobalStreamCapture` redirected to a pipe (it lands on stdin, or on
        `COLUMNS`, and can disagree with what the renderer is painting).
        """
        columns = None
        app = getattr(self, "_application", None)
        if app is not None:
            try:
                columns = app.output.get_size().columns
            except Exception:
                columns = None
        if columns is None:
            try:
                columns = get_terminal_size().columns
            except Exception:
                return None
        width = columns - 4
        return width if width >= 10 else None

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
            queued = cast(int, getattr(self, "queued_message_count", 0))
            return [
                (
                    CFG.LLM_UI_STYLE_THINKING,
                    f" ⏳ {self._assistant_name} is working{dot_str} ",
                ),
                *(
                    [(CFG.LLM_UI_STYLE_STATUS, f" 📥 {queued} queued ")]
                    if queued
                    else []
                ),
                *self._get_token_usage_fragments(),
            ]
        # Persistent Shift+Tab mode indicator (mirrors Claude Code's mode badge
        # near the prompt). `current_cycle_mode` lives on BaseUIModelCommands;
        # guard for lightweight UIs/mocks that don't compose it. See ADR-0073.
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
        # Voice mode indicator (see ADR-0074)
        if getattr(self, "_voice_mode_active", False):
            result.append((CFG.LLM_UI_STYLE_STATUS, " 🎤 VOICE "))
        result.extend(self._get_token_usage_fragments())
        return result

    def _get_token_usage_fragments(self) -> list[tuple[str, str]]:
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
        return [
            (CFG.LLM_UI_STYLE_FAINT, "\n"),
            (f"fg:{CFG.LLM_UI_STYLE_FAINT}", text + " "),
        ]
