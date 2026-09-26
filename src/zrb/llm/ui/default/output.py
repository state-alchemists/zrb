"""Output rendering for the default `UI`.

Carries the logic for appending text to the read-only output buffer
(`append_to_output`) and rendering the info / status bars. Kept separate
from `default_ui.py` so the prompt-toolkit Application setup stays focused.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, TextIO, cast

from zrb.config.config import CFG
from zrb.llm.agent.activity import agent_activity_registry
from zrb.llm.tool.ambient_state import get_session_ownership_key
from zrb.llm.ui.output_chunk import (
    CollapsibleBlockSource,
    merge_into_block,
    merge_output_chunk,
)
from zrb.llm.ui.tracked_spans import TrackedSpans
from zrb.util.cli.help_panel import render_help_panel
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_muted
from zrb.util.cli.terminal import get_terminal_size
from zrb.util.truncate import truncate_display

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from prompt_toolkit.formatted_text import AnyFormattedText

    from zrb.llm.ui.default.ui import UI

logger = logging.getLogger(__name__)

# Short labels + styles for the status-bar Shift+Tab mode badge. Keys match
# `BaseUIModelCommands.current_cycle_mode()` (cycle members plus the off-cycle
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


def _bold(style: str) -> str:
    """A fragment style with ``bold`` appended, or ``bold`` alone when empty."""
    return f"{style} bold" if style else "bold"


def _center_line(fragments: list, total_cols: int) -> list:
    """Horizontally center *fragments* over *total_cols* columns."""
    # lazy: heavy third-party
    from prompt_toolkit.formatted_text.utils import fragment_list_width

    visible_width = fragment_list_width(fragments)
    padding = max(0, (total_cols - visible_width) // 2)
    trailing = max(0, total_cols - visible_width - padding)
    return [("", " " * padding), *fragments, ("", " " * trailing)]


def _render_collapsible_block(
    source: "CollapsibleBlockSource", width: int | None
) -> str:
    return source.full if source.expanded else source.collapsed


class UIOutput:
    """Renders the output field, info bar, and status bar for the default UI."""

    def __init__(self, ui: "UI") -> None:
        self._ui = ui
        self._spans = TrackedSpans(
            get_text=lambda: self.output_text,
            set_text=self.set_output_text,
            get_blocks=lambda: self._ui.rendered_blocks,
            register_block=self._register_collapsed_block,
            append=self._append_progress_line,
        )

    @property
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""
        return self._ui.is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool) -> None:
        self._ui.is_thinking = value

    @property
    def output_text(self) -> str:
        """Get the current text in the output field."""
        return self.output_field.text

    @property
    def output_field(self) -> Any:
        """Public read accessor for the raw output-field widget."""
        return self._ui.output_field

    @property
    def input_field(self) -> Any:
        """Public read accessor for the raw input-field widget."""
        return self._ui.input_field

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

        current_text = self._ui.output_field.text

        # The output window pins itself to the cursor, so follow-the-tail means
        # "keep the cursor on the last line"; scrolling up moves the cursor and
        # freezes the view until the user scrolls back down. Independent of
        # which pane is focused.
        #
        # "Cursor on the last line" == "no newline after the cursor", checked
        # on the raw string: document.cursor_position_row builds the line
        # index, an O(buffer) scan per streamed chunk.
        is_at_last_line = True
        try:
            cursor = self._ui.output_field.buffer.cursor_position
            is_at_last_line = current_text.find("\n", cursor) == -1
        except Exception:
            # Per-chunk render hot path; default to "at last line" if the
            # buffer isn't queryable rather than logging on every token.
            pass
        should_scroll_to_end = is_at_last_line

        content = sep.join([str(value) for value in values]) + end

        # Buffer main-agent output while a confirmation is pending during
        # streaming, so the confirmation prompt is not interleaved with tokens.
        if self._ui.confirmation.current is not None and self._ui.is_thinking:
            self._ui.confirmation.output_buffer.append(content)
            self.schedule_invalidate()
            return

        # While viewing a sub-agent the output pane shows that sub-agent's
        # buffer; main-transcript appends accumulate into the parked snapshot
        # and reappear when the user exits the view (Left).
        saved_main_output = getattr(self._ui, "saved_main_output", None)
        if (
            getattr(self._ui, "viewing_agent_id", None) is not None
            and saved_main_output is not None
        ):
            self._ui.saved_main_output = merge_output_chunk(saved_main_output, content)
            self.schedule_invalidate()
            return

        if kind not in ("text", "todo_progress"):
            content = stylize_muted(content)

        # Handle carriage returns (\r) for status updates. A chunk of an
        # open thinking/final-text block merges at that block's own end,
        # not the buffer tail, so a concurrent writer's line stays outside
        # it — see `merge_into_block`.
        new_text, rebase_from = merge_into_block(
            current_text, content, self._spans.open_block, kind
        )
        if rebase_from >= 0:
            # Absorbing the chunk rewrote the buffer before whatever a
            # concurrent writer had already put after the block, so every span
            # tracked past that point moved with it.
            self._spans.rebase(rebase_from, len(new_text) - len(current_text))

        # No Notification hook per chunk: that event means "the agent needs
        # your attention", and a subprocess per streamed chunk exhausts file
        # descriptors under a real command hook.

        new_cursor_position = (
            len(new_text)
            if should_scroll_to_end
            else self._ui.output_field.buffer.cursor_position
        )
        new_cursor_position = min(max(0, new_cursor_position), len(new_text))

        self._ui.output_field.buffer.set_document(
            Document(new_text, cursor_position=new_cursor_position),
            bypass_readonly=True,
        )
        self.schedule_invalidate()

    def append_markdown(self, markdown_text: str) -> None:
        """Append rendered markdown, remembering the source (public API)."""
        self.append_rendered(markdown_text, self._render_markdown_block)

    def render_markdown(self, markdown_text: str, width: int | None = None) -> str:
        """Render `markdown_text` at `width` (public API).

        Counterpart to `append_markdown` for a caller (the queued-message echo
        splice) that needs the rendered text in hand rather than appended.
        `width` defaults to the current output width, which is also what
        `rewrap_output` passes when it re-renders a tracked block, so the same
        call serves the first render and every re-render after a resize.
        """
        if width is None:
            width = self.output_field_width
        return self._render_markdown_block(markdown_text, width)

    def print_help(self) -> None:
        """Append the help panel as a re-renderable block (public API).

        Overrides `BaseUICommands.print_help` so `/help` re-lays out on resize
        the same way the greeting panel does.
        """
        self.append_rendered(self._ui.get_help_panel(), render_help_panel)

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
            self.set_rendered_block(start, end, source, renderer)

    def set_rendered_block(
        self,
        start: int,
        end: int,
        source: Any,
        renderer: "Callable[[Any, int | None], str]",
    ) -> None:
        """Record ``text[start:end]`` as a re-renderable block (public API).

        The one way a block enters `rendered_blocks`, because two invariants
        hold over that list and neither survives a plain `append`:

        * **Position order.** `rewrap_output` walks the list accumulating the
          length delta of each re-render, and `toggle_collapsible_block_at_cursor`
          stops at the first block past the cursor. A record appended out of
          order makes every later offset in that walk address the wrong text.
          Appending is only in order when the block is at the buffer tail,
          which a collapsed thinking/text block or `finish_shell_output`
          and a re-registered echo are not — so the record is inserted at the
          position its `start` puts it in.
        * **No overlap.** Writing `text[start:end]` replaced whatever was
          there, so any record still covering part of that region describes
          text that no longer exists; re-rendering it would splice over this
          one. Those records are dropped here rather than left to rot.
        """
        blocks = self._ui.rendered_blocks
        blocks[:] = [block for block in blocks if block[0] >= end or block[1] <= start]
        for index, block in enumerate(blocks):
            if block[0] >= end:
                blocks.insert(index, [start, end, source, renderer])
                return
        blocks.append([start, end, source, renderer])

    def append_toggle_block(self, collapsed: str, full: str) -> None:
        """Append a tool-call/result line that can later be expanded in place.

        Styling is applied once here (mirroring what `append_to_output` does
        automatically for `kind="tool_call"`) because `append_rendered`
        inserts via `append_to_output(rendered, end="")` with the default
        `kind="text"`, which skips auto-styling.
        """
        if collapsed == full:
            self.append_to_output(collapsed, end="")
            return
        source = CollapsibleBlockSource(stylize_muted(collapsed), stylize_muted(full))
        self.append_rendered(source, _render_collapsible_block)

    def mark_thinking_block_start(self) -> None:
        """Record where a live-streamed thinking block begins in the buffer.

        Called right before the model's first thinking chunk is printed, so
        `collapse_thinking_block` can later wrap exactly that span. Thinking
        streams live (unlike tool-call args/results, which are collapsed
        from the start) — this is a retroactive collapse, not a withhold.
        """
        self._spans.mark_block_start("thinking")

    def collapse_thinking_block(self, collapsed: str, full: str) -> bool:
        """Collapse the thinking block opened by `mark_thinking_block_start`.

        See `TrackedSpans.collapse_block` for the mechanics and why `full`
        must be the caller's own accumulated text rather than re-read from
        the buffer.
        """
        return self._spans.collapse_block(collapsed, full)

    def mark_text_block_start(self) -> None:
        """Record where the live-streamed final-text response begins.

        Counterpart to `mark_thinking_block_start` for the assistant's reply
        instead of its reasoning — same retroactive-collapse mechanics.
        """
        self._spans.mark_block_start("streaming")

    def collapse_text_block(self, collapsed: str, full: str) -> bool:
        """Collapse the final-text block opened by `mark_text_block_start`.

        `BaseUI.stream_ai_response` appends a markdown-rendered copy of the
        same text separately once the turn finishes; this only replaces the
        raw streamed copy so the response isn't shown twice.
        """
        return self._spans.collapse_block(collapsed, full)

    def update_shell_output(self, key: str, text: str) -> None:
        """Grow or replace `key`'s own live shell-output line with `text`
        (the full accumulated stdout+stderr echo so far) — called on every
        new line while the command runs. See `TrackedSpans.update_shell_output`.
        """
        self._spans.update_shell_output(key, text)

    def finish_shell_output(self, key: str, collapsed: str, full: str) -> bool:
        """Collapse `key`'s live line (opened via `update_shell_output`)
        into `collapsed`, registering it as Ctrl+O-expandable holding
        `full`. Unlike `update_tool_prepare`'s placeholder, this needs
        `rendered_blocks` bookkeeping since the point is to let the user
        expand back to the full output.

        `full` is the caller's own accumulated echo (see
        `StreamCapture.echoed_text`), not re-read from the buffer — same
        "don't trust a `\\r`-mangled screen" contract as
        `collapse_thinking_block`.
        """
        return self._spans.finish_shell_output(key, collapsed, full)

    def update_tool_prepare(self, key: str, text: str) -> None:
        """Print or update `key`'s own "Prepare tool parameters" line.

        Passing an empty `text` erases the line and stops tracking `key`.
        Not a `CollapsibleBlockSource` / `rendered_blocks` entry: this line
        never needs Ctrl+O expansion.
        """
        self._spans.update_tool_prepare(key, text)

    def toggle_collapsible_block_at_cursor(self) -> bool:
        """Expand/collapse the collapsible block at-or-before the output
        cursor (a tool call, a tool result, or a collapsed thinking block).

        Returns whether a block was found and toggled.
        """
        try:
            offset = self._ui.output_field.buffer.cursor_position
        except Exception:
            return False
        return self._spans.toggle_at(offset)

    def _register_collapsed_block(
        self, start: int, end: int, source: CollapsibleBlockSource
    ) -> None:
        self.set_rendered_block(start, end, source, _render_collapsible_block)

    def _append_progress_line(self, text: str) -> None:
        self.append_to_output(text, end="", kind="progress")

    def rewrap_output(self) -> None:
        """Re-render tracked blocks at the current width (public API).

        Called from the app's after-render hook; a no-op unless the terminal
        width actually changed.
        """
        width = self.output_field_width
        if width == self._ui.rendered_width:
            return
        self._ui.rendered_width = width
        if not self._ui.rendered_blocks:
            return
        # ponytail: splices by recorded offsets, which assumes nothing rewrote
        # the transcript inside a tracked span (only the trailing status line
        # is ever rewritten, via \r). If that stops holding, store the rendered
        # text per block and rebuild the whole buffer from the block list.
        text = self.output_text
        shift = 0
        for block in self._ui.rendered_blocks:
            start, end = block[0] + shift, block[1] + shift
            rendered = block[3](block[2], width)
            text = text[:start] + rendered + text[end:]
            block[0], block[1] = start, start + len(rendered)
            shift += len(rendered) - (end - start)
        self.set_output_text(text)

    def _render_markdown_block(self, markdown_text: str, width: int | None) -> str:
        return render_markdown(
            markdown_text, width=width, theme=self._ui.markdown_theme
        )

    def replace_output_span(self, start: int, end: int, replacement: str) -> bool:
        """Replace ``text[start:end]`` in the output buffer.

        Used to rewrite a queued message's echoed line in place after an edit.
        Every tracked offset past the span — rendered blocks, the keyed live
        lines, the open collapsible block — shifts by the length delta; see
        `TrackedSpans.replace`. Returns ``False`` when the span no longer
        exists (the echo was confirmation-buffered or the buffer was rewritten
        since).
        """
        return self._spans.replace(start, end, replacement)

    def set_output_text(self, text: str) -> None:
        # lazy: heavy third-party
        from prompt_toolkit.document import Document

        buffer = self._ui.output_field.buffer
        follows_tail = buffer.cursor_position >= len(buffer.text)
        cursor = len(text) if follows_tail else min(buffer.cursor_position, len(text))
        buffer.set_document(
            Document(text, cursor_position=cursor), bypass_readonly=True
        )
        self.schedule_invalidate()

    def schedule_invalidate(self):
        if self._ui.pending_invalidate:
            return
        self._ui.pending_invalidate = True

        async def _do_invalidate():
            await asyncio.sleep(0.016)
            self._ui.pending_invalidate = False
            self._ui.invalidate_ui()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._ui.pending_invalidate = False
            self._ui.invalidate_ui()
            return
        self._ui.invalidate_task = loop.create_task(_do_invalidate())

    @property
    def output_field_width(self) -> int | None:
        """Get the output field width.

        Asks the running application first: its output is a dup of the real
        stdout, while `get_terminal_size` has to probe fds 1/2 that
        `GlobalStreamCapture` redirected to a pipe (it lands on stdin, or on
        `COLUMNS`, and can disagree with what the renderer is painting).
        """
        columns = None
        app = self._ui.application if self._ui.is_application_built else None
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
        """Build the bar as (style, text) fragments rather than HTML.

        This lets the INFO_* knobs hold full prompt_toolkit style strings
        (e.g. "ansired bold"), consistent with every other LLM_UI_STYLE_*
        field, and avoids embedding runtime strings (model/cwd/git) into
        HTML where '<'/'&' would break markup.
        """
        model_name = self._model_name()

        line1 = [
            ("", " 🤖 "),
            ("bold", "Model:"),
            ("", f" {model_name} | 💬 "),
            ("bold", "Session:"),
            ("", f" {self._ui.conversation_session_name} "),
        ]
        sub_agent_frag = self._sub_agent_fragment()
        if sub_agent_frag:
            line1 += sub_agent_frag

        line2 = [
            ("", " 📋 "),
            ("bold", "Plan Mode:"),
            ("", " "),
            self._plan_fragment(),
            ("", " | 🤠 "),
            ("bold", "YOLO:"),
            ("", " "),
            self._yolo_fragment(),
            ("", " "),
        ]
        line3 = [
            ("", " 📂 "),
            ("bold", "Dir:"),
            ("", f" {self._ui.cwd} | 🌿 "),
            ("bold", "Git:"),
            ("", f" {self._ui.git_info} "),
        ]

        total_cols = get_terminal_size().columns
        return [
            *_center_line(line1, total_cols),
            ("", "\n"),
            *_center_line(line2, total_cols),
            ("", "\n"),
            *_center_line(line3, total_cols),
        ]

    def _model_name(self) -> str:
        """The model label shown in the info bar."""
        model_name = "Unknown"
        if self._ui.model:
            if isinstance(self._ui.model, str):
                model_name = self._ui.model
            elif hasattr(self._ui.model, "model_name"):
                model_name = getattr(self._ui.model, "model_name")
            else:
                model_name = str(self._ui.model)
        return model_name

    def _plan_fragment(self) -> tuple:
        """The Plan-Mode on/off fragment (bold while active)."""
        if getattr(self._ui, "plan_mode_active", False):
            return (_bold(CFG.LLM_UI_STYLE_INFO_PLAN_ON), "On ")
        return (CFG.LLM_UI_STYLE_INFO_PLAN_OFF, "Off")

    def _yolo_fragment(self) -> tuple:
        """The YOLO mode fragment: on, partial (tool subset), or off."""
        _yolo = self._ui.yolo
        if _yolo is True:
            return (_bold(CFG.LLM_UI_STYLE_INFO_YOLO_ON), "ON ")
        if isinstance(_yolo, frozenset) and _yolo:
            tools_str = ",".join(sorted(_yolo))
            return (_bold(CFG.LLM_UI_STYLE_INFO_YOLO_PARTIAL), f"[{tools_str}]")
        return (CFG.LLM_UI_STYLE_INFO_YOLO_OFF, "OFF")

    def _sub_agent_fragment(self) -> "list | None":
        """Fragments announcing an active persona or viewed sub-agent.

        The UI clue that /load swapped which persona is
        driving new messages — absent (bar unchanged) while driving the
        main agent, mirroring how the activity panel collapses when idle.
        Extended (same wording) to announce the sub-agent whose live view
        the output pane currently shows (UIAgentPicker).
        """
        persona = getattr(self._ui, "persona", None)
        active_persona = None if persona is None else persona.active_subagent
        viewing_agent_id = getattr(self._ui, "viewing_agent_id", None)
        viewing_name = None
        if viewing_agent_id:
            # lazy: transitively heavy via internal — live_session.py imports
            # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
            from zrb.llm.agent.subagent.live_session import (
                live_subagent_session_registry,
            )

            session = live_subagent_session_registry.get(
                get_session_ownership_key(self._ui.conversation_session_name),
                viewing_agent_id,
            )
            if session is not None:
                viewing_name = session.agent_name
        if not (active_persona or viewing_name):
            return None
        name = viewing_name if viewing_name is not None else active_persona
        suffix = " (viewing · ← back)" if viewing_name else ""
        return [
            ("", "| 🎭 "),
            ("bold", "Sub-agent:"),
            ("", f" {name}{suffix} "),
        ]

    def get_agent_activity_text(self) -> "AnyFormattedText":
        """One line per running sub-agent: #ordinal name · task — activity.

        This panel is the legend for the [name #ordinal] prefixes in the output
        stream. Empty when nothing is delegating, so it collapses to zero height.
        Refreshed by the app's periodic redraw (LLM_UI_REFRESH_INTERVAL).

        While a sub-agent's live view is showing, the panel stops listing the
        other sub-agents and advertises the way back to the parent session
        instead (Left Arrow).
        """
        viewing_agent_id = getattr(self._ui, "viewing_agent_id", None)
        if viewing_agent_id is not None:
            return [(CFG.LLM_UI_STYLE_FAINT, "Press ← to return to the parent")]
        agents = agent_activity_registry.active(
            session_id=get_session_ownership_key(self._ui.conversation_session_name)
        )
        # The Down-Arrow picker lists every live (running or just-finished)
        # sub-agent session, so the panel advertises it whenever one is
        # tracked — not only while something is currently running.
        # lazy: transitively heavy via internal — live_session.py imports
        # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
        from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

        live = live_subagent_session_registry.active(
            session_id=get_session_ownership_key(self._ui.conversation_session_name)
        )
        if not agents and not live:
            return []
        lines: list = []
        for agent in agents:
            label = f" 🔧 #{agent.ordinal} {agent.name}"
            if agent.task:
                label += f" · {_truncate(agent.task, 50)}"
            if agent.last_line:
                label += f" — {_truncate(agent.last_line, 40)}"
            lines.append((CFG.LLM_UI_STYLE_THINKING, label))
        if agents:
            lines.append((CFG.LLM_UI_STYLE_FAINT, " ↓ talk to a sub-agent"))
        frags: list = []
        for style, text in lines:
            frags.append((style, text))
            frags.append(("", "\n"))
        return frags[:-1]  # drop trailing newline so height == line count

    def get_status_bar_text(self) -> "AnyFormattedText":
        if self._ui.confirmation.current is not None:
            dots = getattr(self, "_confirmation_dots", 0)
            next_dots = (dots + 1) % 4
            setattr(self, "_confirmation_dots", next_dots)
            dot_str = "." * next_dots + " " * (3 - next_dots)
            assistant_name = self._ui.assistant_name
            return [
                (
                    CFG.LLM_UI_STYLE_CONFIRMATION,
                    f" 👋 {assistant_name} is waiting for confirmation{dot_str} ",
                )
            ]
        if self.is_thinking:
            dots = getattr(self, "_thinking_dots", 0)
            next_dots = (dots + 1) % 4
            setattr(self, "_thinking_dots", next_dots)
            dot_str = "." * next_dots + " " * (3 - next_dots)
            queued = cast(int, getattr(self._ui, "queued_message_count", 0))
            return [
                (
                    CFG.LLM_UI_STYLE_THINKING,
                    f" ⏳ {self._ui.assistant_name} is working{dot_str} ",
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
        # guard for lightweight UIs/mocks that don't compose it. See ADR-0075.
        get_mode = getattr(self._ui, "current_cycle_mode", None)
        mode = cast(str, get_mode()) if callable(get_mode) else "normal"
        result: list = [
            (CFG.LLM_UI_STYLE_STATUS, " 🚀 Ready "),
            (
                _get_mode_status_style(mode),
                f" {_MODE_STATUS_LABELS.get(mode, mode)} ",
            ),
            (f"fg:{CFG.LLM_UI_STYLE_FAINT}", "shift+tab to cycle "),
        ]
        # Voice mode indicator (see ADR-0076)
        voice = getattr(self._ui, "voice", None)
        if voice is not None and voice.mode_active:
            result.append((CFG.LLM_UI_STYLE_STATUS, " 🎤 VOICE "))
        result.extend(self._get_token_usage_fragments())
        return result

    def _get_token_usage_fragments(self) -> list[tuple[str, str]]:
        """Session token totals as status-bar fragments; empty until first run."""
        usage_part = getattr(self._ui, "usage", None)
        input_tokens, output_tokens = cast(
            tuple[int, int], getattr(usage_part, "session_token_usage", (0, 0))
        )
        if not input_tokens and not output_tokens:
            return []
        text = f" 💸 {_fmt_tokens(input_tokens)} in · {_fmt_tokens(output_tokens)} out"
        cached = cast(int, getattr(usage_part, "session_cache_read_tokens", 0))
        if cached:
            text += f" · {_fmt_tokens(cached)} cached"
        context = cast(int, getattr(usage_part, "context_tokens", 0))
        if context:
            text += f" · 🧠 {_fmt_tokens(context)} ctx"
        return [
            (CFG.LLM_UI_STYLE_FAINT, "\n"),
            (f"fg:{CFG.LLM_UI_STYLE_FAINT}", text + " "),
        ]
