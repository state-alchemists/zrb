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


def _merge_output_chunk(current_text: str, content: str) -> str:
    """Append `content` to `current_text`, resolving ``\\r`` status updates.

    Carriage returns signal an in-place status rewrite: the last line since
    the most recent newline is replaced by the content up to each ``\\r``.
    """
    if "\r" not in content:
        return current_text + content
    last_newline = current_text.rfind("\n")
    if last_newline == -1:
        previous = ""
        last = current_text
    else:
        previous = current_text[: last_newline + 1]
        last = current_text[last_newline + 1 :]
    combined = last + content
    resolved = re.sub(r"[^\n]*\r", "", combined)
    return previous + resolved


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


class CollapsibleBlockSource:
    """Rendered-block payload for a collapsible line (tool-call/result,
    thinking, ...).

    Plugs into `UIOutput.rendered_blocks` as a `source` alongside the
    markdown/help-panel sources already tracked there, so `rewrap_output`
    re-renders it (and shifts later blocks) for free on resize.
    """

    __slots__ = ("collapsed", "full", "expanded")

    def __init__(self, collapsed: str, full: str):
        self.collapsed = collapsed
        self.full = full
        self.expanded = False


def _render_collapsible_block(
    source: "CollapsibleBlockSource", width: int | None
) -> str:
    return source.full if source.expanded else source.collapsed


class UIOutput:
    """Renders the output field, info bar, and status bar for the default UI."""

    def __init__(self, ui: "UI") -> None:
        self._ui = ui
        # Set by `mark_thinking_block_start`/`mark_text_block_start`; consumed
        # (and cleared) by `collapse_thinking_block`/`collapse_text_block`.
        # Purely local, transient per-turn state — not shared with anything
        # else, so it lives here rather than on `ui`. One slot suffices: a
        # thinking block and the final-text block are never open at the same
        # time (`StreamEventHandler` always closes one before opening the
        # other), so there is never more than one live collapsible block to
        # track.
        self._collapsible_block_start: int | None = None
        # Per-tool-call span for `update_tool_prepare` — unlike the single
        # slot above, several tool calls can be preparing arguments at once
        # (parallel tool calls), each needing its own independently
        # updatable span.
        self._tool_prepare_spans: dict[str, tuple[int, int]] = {}
        # Keyed like `_tool_prepare_spans` (not the single slot above) for
        # the same reason: if the tool-execution framework ever runs more
        # than one Shell call concurrently, each command's live output must
        # collapse independently. Only a start offset is tracked — unlike
        # `update_tool_prepare`, a shell command's echo grows via ordinary
        # appends (not a live replace), so no "current end" bookkeeping is
        # needed until the one final collapse.
        self._shell_output_spans: dict[str, tuple[int, int]] = {}

    @property
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""
        return self._ui.is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool) -> None:
        self._ui.is_thinking = value

    @property
    def current_confirmation(self) -> "asyncio.Future[str] | None":
        """The pending tool-call confirmation future, if any."""
        return self._ui.current_confirmation

    @current_confirmation.setter
    def current_confirmation(self, value: "asyncio.Future[str] | None") -> None:
        self._ui.current_confirmation = value

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
        if self._ui.current_confirmation is not None and self._ui.is_thinking:
            self._ui.confirmation_output_buffer.append(content)
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
            self._ui.saved_main_output = _merge_output_chunk(saved_main_output, content)
            self.schedule_invalidate()
            return

        if kind not in ("text", "todo_progress"):

            content = stylize_muted(content)

        # Handle carriage returns (\r) for status updates
        new_text = _merge_output_chunk(current_text, content)

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
            self._ui.rendered_blocks.append([start, end, source, renderer])

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
        self._mark_collapsible_block_start()

    def collapse_thinking_block(self, collapsed: str, full: str) -> bool:
        """Collapse the thinking block opened by `mark_thinking_block_start`.

        See `_collapse_collapsible_block` for the mechanics and why `full`
        must be the caller's own accumulated text rather than re-read from
        the buffer.
        """
        return self._collapse_collapsible_block(collapsed, full)

    def mark_text_block_start(self) -> None:
        """Record where the live-streamed final-text response begins.

        Counterpart to `mark_thinking_block_start` for the assistant's reply
        instead of its reasoning — same retroactive-collapse mechanics.
        """
        self._mark_collapsible_block_start()

    def collapse_text_block(self, collapsed: str, full: str) -> bool:
        """Collapse the final-text block opened by `mark_text_block_start`.

        `BaseUI.stream_ai_response` appends a markdown-rendered copy of the
        same text separately once the turn finishes; this only replaces the
        raw streamed copy so the response isn't shown twice.
        """
        return self._collapse_collapsible_block(collapsed, full)

    def _mark_collapsible_block_start(self) -> None:
        self._collapsible_block_start = len(self.output_text)

    def _collapse_collapsible_block(self, collapsed: str, full: str) -> bool:
        """Shared mechanics for `collapse_thinking_block`/`collapse_text_block`.

        See `_splice_collapsed_span` for the mechanics and why `full` must
        be the caller's own accumulated text. A no-op if no block was
        marked (e.g. this UI missed the start signal).
        """
        start = self._collapsible_block_start
        self._collapsible_block_start = None
        if start is None:
            return False
        return self._splice_collapsed_span(start, collapsed, full)

    def update_shell_output(self, key: str, text: str) -> None:
        """Grow or replace `key`'s own live shell-output line with `text`
        (the full accumulated stdout+stderr echo so far) — called on every
        new line while the command runs.

        Shares mechanics with `update_tool_prepare` (see
        `_update_keyed_line`): the *first* regression attempt at this
        feature marked one offset and let two concurrently-running Shell
        commands' echo interleave into the buffer between mark and
        collapse — whichever command's block collapsed first devoured the
        *other's* interleaved lines too, since "everything between start
        and current end" doesn't hold when a second writer is growing its
        own content in the same window. Replacing this key's own span
        wholesale on every update — never touching anything outside it —
        is what makes two commands' live output safe to interleave.
        """
        self._update_keyed_line(self._shell_output_spans, key, text)

    def finish_shell_output(self, key: str, collapsed: str, full: str) -> bool:
        """Collapse `key`'s live line (opened via `update_shell_output`)
        into `collapsed`, registering it as Ctrl+O-expandable holding
        `full`. Unlike `update_tool_prepare`'s placeholder, this needs
        `rendered_blocks` bookkeeping since the point is to let the user
        expand back to the full output.

        `full` is the caller's own accumulated echo (see
        `StreamCapture.echoed_text`), not re-read from the buffer — same
        "don't trust a `\\r`-mangled screen" contract as
        `_collapse_collapsible_block`. Uses this key's own tracked `end`,
        not `len(output_text)`: unlike the single-slot tracker, other keys'
        own live lines may already have grown past this one by the time it
        finishes.
        """
        span = self._shell_output_spans.pop(key, None)
        if span is None or not full:
            return False
        start, end = span
        source = CollapsibleBlockSource(stylize_muted(collapsed), stylize_muted(full))
        if not self.replace_output_span(start, end, source.collapsed):
            return False
        self._ui.rendered_blocks.append(
            [start, start + len(source.collapsed), source, _render_collapsible_block]
        )
        return True

    def _splice_collapsed_span(self, start: int, collapsed: str, full: str) -> bool:
        """Shared low-level mechanics: splice `collapsed` over `[start, end)`
        (`end` is the current buffer length) and register the span as
        Ctrl+O-expandable. Shared by the single-slot tracker
        (`_collapse_collapsible_block`, thinking/text) and the keyed one
        (`collapse_shell_output_block`) — both just resolve `start`
        differently before calling this.

        `full` is the caller's own accumulated text, deliberately NOT
        re-read from the buffer: a stray carriage return anywhere in a
        streamed chunk can rewrite or erase part of the *rendered* line
        (see `append_to_output`'s `\\r` handling, built for progress
        spinners but applying to any text), so reconstructing "the full
        text" from what currently sits on screen would silently inherit
        that erasure. A no-op if nothing was actually accumulated.
        """
        if not full:
            return False
        end = len(self.output_text)
        if end <= start:
            return False
        source = CollapsibleBlockSource(stylize_muted(collapsed), stylize_muted(full))
        if not self.replace_output_span(start, end, source.collapsed):
            return False
        self._ui.rendered_blocks.append(
            [start, start + len(source.collapsed), source, _render_collapsible_block]
        )
        return True

    def update_tool_prepare(self, key: str, text: str) -> None:
        """Print or update `key`'s own "Prepare tool parameters" line.

        See `_update_keyed_line` for the mechanics. Passing an empty `text`
        erases the line and stops tracking `key`.

        Not a `CollapsibleBlockSource` / `rendered_blocks` entry: this line
        never needs Ctrl+O expansion, so it skips that bookkeeping entirely
        (unlike `update_shell_output`'s counterpart, `finish_shell_output`).
        """
        self._update_keyed_line(self._tool_prepare_spans, key, text)

    def _update_keyed_line(
        self, spans: "dict[str, tuple[int, int]]", key: str, text: str
    ) -> None:
        """Shared mechanics for `update_tool_prepare`/`update_shell_output`:
        grow or replace `key`'s own tracked span in `spans` with `text`.

        The first call for a given `key` appends `text` fresh (auto-styled
        via `kind="progress"`) and starts tracking its span; every later
        call replaces exactly that span (re-styled manually, since
        `replace_output_span` doesn't apply `kind`-based styling) — never
        anything else. This is what makes two keys' own lines safe to grow
        concurrently: the old `\\r`-based "erase whatever is currently the
        last line" trick (tool-prepare's original implementation) and the
        "mark once, let anything get appended, collapse the whole span"
        trick (shell-output's original implementation) both broke the
        moment a second key's content landed inside the first key's own
        span. Passing an empty `text` erases the line and stops tracking
        `key`.
        """
        span = spans.get(key)
        if span is None:
            if not text:
                return
            start = len(self.output_text)
            self.append_to_output(text, end="", kind="progress")
            spans[key] = (start, len(self.output_text))
            return
        start, end = span
        styled = stylize_muted(text) if text else ""
        if not self.replace_output_span(start, end, styled):
            return
        if text:
            spans[key] = (start, start + len(styled))
        else:
            spans.pop(key, None)

    def toggle_collapsible_block_at_cursor(self) -> bool:
        """Expand/collapse the collapsible block at-or-before the output
        cursor (a tool call, a tool result, or a collapsed thinking block).

        `rendered_blocks` is append-ordered == position-ordered (the same
        invariant `rewrap_output` relies on), so this picks the *last*
        collapsible block at-or-before the cursor — "the block I'm looking
        at," or the most recent one when the cursor is following the tail.
        Returns whether a block was found and toggled.
        """
        try:
            offset = self._ui.output_field.buffer.cursor_position
        except Exception:
            return False
        target = None
        for block in self._ui.rendered_blocks:
            if block[0] > offset:
                break
            if isinstance(block[2], CollapsibleBlockSource):
                target = block
        if target is None:
            return False
        source = target[2]
        new_expanded = not source.expanded
        new_text = source.full if new_expanded else source.collapsed
        if not self.replace_output_span(target[0], target[1], new_text):
            return False
        source.expanded = new_expanded
        target[1] = target[0] + len(new_text)
        return True

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
        Tracked rendered blocks starting at or after the replaced span are
        shifted by the length delta — the same bookkeeping `rewrap_output`
        keeps, so a later re-wrap still splices at the right offsets. Other
        keys' own tracked spans (`_tool_prepare_spans`, see
        `update_tool_prepare`; `_shell_output_spans`, see
        `update_shell_output`) get the same shift — one key's own span
        growing/shrinking/resolving must not invalidate another's still-open
        span. Returns ``False`` when the span no longer exists (the echo was
        confirmation-buffered or the buffer was rewritten since).
        """
        text = self.output_text
        if end > len(text):
            return False
        delta = len(replacement) - (end - start)
        new_text = text[:start] + replacement + text[end:]
        if delta:
            for block in self._ui.rendered_blocks:
                if block[0] >= end:
                    block[0] += delta
                    block[1] += delta
            for spans in (self._tool_prepare_spans, self._shell_output_spans):
                for key, (span_start, span_end) in list(spans.items()):
                    if span_start >= end:
                        spans[key] = (span_start + delta, span_end + delta)
        self.set_output_text(new_text)
        return True

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
        app = getattr(self._ui, "application", None)
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
        if self._ui.model:
            if isinstance(self._ui.model, str):
                model_name = self._ui.model
            elif hasattr(self._ui.model, "model_name"):
                model_name = getattr(self._ui.model, "model_name")
            else:
                model_name = str(self._ui.model)

        # Build the bar as (style, text) fragments rather than HTML. This lets the
        # INFO_* knobs hold full prompt_toolkit style strings (e.g. "ansired bold"),
        # consistent with every other LLM_UI_STYLE_* field, and avoids embedding
        # runtime strings (model/cwd/git) into HTML where '<'/'&' would break markup.
        def _bold(style: str) -> str:
            return f"{style} bold" if style else "bold"

        _yolo = self._ui.yolo
        if _yolo is True:
            yolo_frag = (_bold(CFG.LLM_UI_STYLE_INFO_YOLO_ON), "ON ")
        elif isinstance(_yolo, frozenset) and _yolo:
            tools_str = ",".join(sorted(_yolo))
            yolo_frag = (_bold(CFG.LLM_UI_STYLE_INFO_YOLO_PARTIAL), f"[{tools_str}]")
        else:
            yolo_frag = (CFG.LLM_UI_STYLE_INFO_YOLO_OFF, "OFF")

        if getattr(self._ui, "plan_mode_active", False):
            plan_frag = (_bold(CFG.LLM_UI_STYLE_INFO_PLAN_ON), "On ")
        else:
            plan_frag = (CFG.LLM_UI_STYLE_INFO_PLAN_OFF, "Off")

        line1 = [
            ("", " 🤖 "),
            ("bold", "Model:"),
            ("", f" {model_name} | 💬 "),
            ("bold", "Session:"),
            ("", f" {self._ui.conversation_session_name} "),
        ]
        # Item 4, Phase D: the UI clue that /load swapped which persona is
        # driving new messages — absent (bar unchanged) while driving the
        # main agent, mirroring how the activity panel collapses when idle.
        # Extended (same wording) to announce the sub-agent whose live view
        # the output pane currently shows (UIAgentPicker).
        active_persona = getattr(self._ui, "active_subagent_persona", None)
        viewing_agent_id = getattr(self._ui, "viewing_agent_id", None)
        viewing_name = None
        if viewing_agent_id:
            # lazy: transitively heavy via internal — live_session.py imports
            # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
            from zrb.llm.agent.subagent.live_session import (
                live_subagent_session_registry,
            )

            session = live_subagent_session_registry.get(
                self._ui.conversation_session_name, viewing_agent_id
            )
            if session is not None:
                viewing_name = session.agent_name
        if active_persona or viewing_name:
            name = viewing_name if viewing_name is not None else active_persona
            suffix = " (viewing · ← back)" if viewing_name else ""
            line1 += [
                ("", "| 🎭 "),
                ("bold", "Sub-agent:"),
                ("", f" {name}{suffix} "),
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
            ("", f" {self._ui.cwd} | 🌿 "),
            ("bold", "Git:"),
            ("", f" {self._ui.git_info} "),
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

        While a sub-agent's live view is showing, the panel stops listing the
        other sub-agents and advertises the way back to the parent session
        instead (Left Arrow).
        """
        viewing_agent_id = getattr(self._ui, "viewing_agent_id", None)
        if viewing_agent_id is not None:
            return [(CFG.LLM_UI_STYLE_FAINT, "Press ← to return to the parent")]
        agents = agent_activity_registry.active(
            session_id=self._ui.conversation_session_name
        )
        # The Down-Arrow picker lists every live (running or just-finished)
        # sub-agent session, so the panel advertises it whenever one is
        # tracked — not only while something is currently running.
        # lazy: transitively heavy via internal — live_session.py imports
        # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
        from zrb.llm.agent.subagent.live_session import (
            live_subagent_session_registry,
        )

        live = live_subagent_session_registry.active(
            session_id=self._ui.conversation_session_name
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
        if self.current_confirmation is not None:
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
        if getattr(self._ui, "voice_mode_active", False):
            result.append((CFG.LLM_UI_STYLE_STATUS, " 🎤 VOICE "))
        result.extend(self._get_token_usage_fragments())
        return result

    def _get_token_usage_fragments(self) -> list[tuple[str, str]]:
        """Session token totals as status-bar fragments; empty until first run."""
        input_tokens, output_tokens = cast(
            tuple[int, int], getattr(self._ui, "session_token_usage", (0, 0))
        )
        if not input_tokens and not output_tokens:
            return []
        text = f" 💸 {_fmt_tokens(input_tokens)} in · {_fmt_tokens(output_tokens)} out"
        cached = cast(int, getattr(self._ui, "session_cache_read_tokens", 0))
        if cached:
            text += f" · {_fmt_tokens(cached)} cached"
        context = cast(int, getattr(self._ui, "context_tokens", 0))
        if context:
            text += f" · 🧠 {_fmt_tokens(context)} ctx"
        return [
            (CFG.LLM_UI_STYLE_FAINT, "\n"),
            (f"fg:{CFG.LLM_UI_STYLE_FAINT}", text + " "),
        ]
