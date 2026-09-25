"""An `AnyUI` that buffers its output instead of writing it through.

Used when several sub-agents run in parallel: each gets one of these, so their
interleaved output is collected and flushed as a block rather than shredded
across the terminal, while `ask`-style prompts are forwarded to the real UI one
at a time under a shared lock.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TextIO

from zrb.llm.agent.activity import agent_activity_registry
from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.output_chunk import (
    CollapsibleBlockSource,
    OpenCollapsibleBlock,
    merge_into_block,
    rebase_tracked_spans,
)
from zrb.llm.ui.state_defaults import UIStateDefaultsMixin
from zrb.util.cli.style import stylize_muted

if TYPE_CHECKING:
    from zrb.llm.agent.types import RequestUsage, RunUsage
    from zrb.llm.ui.any_ui import ChoiceSpec


class BufferedUI(UIStateDefaultsMixin, AnyUI):
    """UI wrapper that buffers all output and forwards asks to parent sequentially."""

    def __init__(
        self,
        wrapped_ui: AnyUI,
        prefix: str = "",
        shared_lock: asyncio.Lock | None = None,
        session_id: str = "",
    ):
        self._wrapped = wrapped_ui
        self._prefix = prefix
        self._buffer: list[str] = []
        self._merged_output: str = ""
        # Toggle-block tracking for Ctrl+O expand/collapse in this sub-agent's
        # own live view — independently scoped from the main transcript's
        # (UIOutput.rendered_blocks); see append_toggle_block below.
        self._rendered_blocks: list = []
        # Set by mark_thinking_block_start/mark_text_block_start; consumed by
        # collapse_thinking_block/collapse_text_block. One slot suffices —
        # see UIOutput's matching field for why.
        self._collapsible_block: OpenCollapsibleBlock | None = None
        # Per-tool-call span for update_tool_prepare — see UIOutput's
        # matching field for why this one is keyed instead of a single slot.
        self._tool_prepare_spans: dict[str, tuple[int, int]] = {}
        # Per-shell-command span for update_shell_output — see UIOutput's
        # matching field for why this is keyed too.
        self._shell_output_spans: dict[str, tuple[int, int]] = {}
        # Set by run_agent_task so buffered output also feeds the activity panel.
        self._agent_id: str | None = None
        # Scopes activity-panel updates to the session that started this
        # delegation, so a process hosting multiple sessions doesn't bleed one
        # session's sub-agent activity into another's.
        self._session_id = session_id
        # Use provided shared lock (for parallel agents) or create own lock
        self._lock = shared_lock if shared_lock is not None else asyncio.Lock()

    def set_activity_id(self, agent_id: str) -> None:
        """Route this sub-agent's output lines to the activity registry."""
        self._agent_id = agent_id

    def set_label(self, prefix: str) -> None:
        """Set the per-line output prefix (e.g. ``[generalist #1] ``)."""
        self._prefix = prefix

    @property
    def label(self) -> str:
        """The output prefix without surrounding whitespace (e.g. ``[generalist #1]``)."""
        return self._prefix.strip()

    @property
    def parent_ui(self) -> AnyUI:
        """The UI this buffer flushes to (the parent agent's UI).

        Public counterpart of the ``wrapped_ui`` constructor argument, so the
        live-session continuation path can hand the parent UI a synthesized
        message (``submit_message``) without reading ``_wrapped``.
        """
        return self._wrapped

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        # The lock guards only the parent write, so sibling fan-out agents'
        # writes don't interleave. It must not wrap the wait for the answer,
        # or every sibling's approval would serialize behind the first and
        # never reach the shared confirmation queue.
        async with self._lock:
            # Shown on the parent so the user sees what is being approved
            # without opening the sub-agent's live view.
            if output_to_parent:
                self._wrapped.append_to_output(output_to_parent, end="")
            prefixed_prompt = (
                f"{self._prefix}{prompt}"
                if self._prefix and prompt.strip() != ""
                else prompt
            )
        # Keep the originating agent's id through nested delegation; only the
        # layer closest to the caller stamps its own.
        return await self._wrapped.ask_user(
            prefixed_prompt,
            agent_id=agent_id if agent_id is not None else self._agent_id,
        )

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        text = sep.join(str(v) for v in values) + end
        # The activity panel renders plain text and would show raw ANSI, so
        # it gets the unstyled line; only the buffer is styled.
        if self._agent_id:
            agent_activity_registry.update(
                self._agent_id, text, session_id=self._session_id
            )

        # As in UIOutput: everything but text/todo_progress is muted.
        styled_text = (
            stylize_muted(text) if kind not in ("text", "todo_progress") else text
        )
        # A chunk of an open thinking/final-text block merges at that
        # block's own end, not the buffer tail, so a concurrent writer's
        # line stays outside it — see `merge_into_block`.
        previous = self._merged_output
        self._merged_output, rebase_from = merge_into_block(
            previous, styled_text, self._collapsible_block, kind
        )
        if rebase_from >= 0:
            self._rebase_tracked_spans(
                rebase_from, len(self._merged_output) - len(previous)
            )
        self._buffer.append(styled_text)

    def _replace_span(self, start: int, end: int, replacement: str) -> bool:
        """Splice ``self._merged_output[start:end]`` with `replacement` in
        place, shifting later `self._rendered_blocks`,
        `self._tool_prepare_spans`, and `self._shell_output_spans` entries
        by the length delta. Mirrors `UIOutput.replace_output_span` minus
        the prompt_toolkit `Document`/cursor-follow/`schedule_invalidate`
        concerns, which don't apply to a plain accumulating string.
        """
        if end > len(self._merged_output):
            return False
        delta = len(replacement) - (end - start)
        self._merged_output = (
            self._merged_output[:start] + replacement + self._merged_output[end:]
        )
        self._rebase_tracked_spans(end, delta)
        block = self._collapsible_block
        if delta and block is not None and block.start >= end:
            block.start += delta
            block.end += delta
        return True

    def _rebase_tracked_spans(self, after: int, delta: int) -> None:
        """Shift every tracked offset at or past `after` by `delta`.

        Mirrors `UIOutput._rebase_tracked_spans` — shared by `_replace_span`
        and the collapsible-block insert in `append_to_output`, the two paths
        that rewrite the buffer somewhere other than the tail. The open block
        is not shifted here; see that method for why.
        """
        rebase_tracked_spans(
            self._rendered_blocks,
            (self._tool_prepare_spans, self._shell_output_spans),
            after,
            delta,
        )

    def append_toggle_block(self, collapsed: str, full: str) -> None:
        """Append a tool-call/result line that can later be expanded in
        place — this sub-agent's own counterpart to
        `UIOutput.append_toggle_block`. Styling is applied once here, same
        as there: this inserts via `append_to_output(rendered, end="")` with
        the default `kind="text"`, which skips the kind-based auto-styling
        `append_to_output` otherwise applies.
        """
        if collapsed == full:
            self.append_to_output(collapsed, end="")
            return
        source = CollapsibleBlockSource(stylize_muted(collapsed), stylize_muted(full))
        start = len(self._merged_output)
        self.append_to_output(source.collapsed, end="")
        self._rendered_blocks.append([start, len(self._merged_output), source])

    def record_tool_call_block(self, collapsed: str, full: str) -> None:
        self.append_toggle_block(collapsed, full)

    def mark_thinking_block_start(self) -> None:
        self._mark_collapsible_block_start("thinking")

    def collapse_thinking_block(self, collapsed: str, full: str) -> bool:
        """Collapse the thinking block opened by `mark_thinking_block_start`.

        See `_collapse_collapsible_block` for the mechanics.
        """
        return self._collapse_collapsible_block(collapsed, full)

    def mark_text_block_start(self) -> None:
        """Counterpart to `mark_thinking_block_start` for the assistant's
        final-text reply instead of its reasoning."""
        self._mark_collapsible_block_start("streaming")

    def collapse_text_block(self, collapsed: str, full: str) -> bool:
        """Collapse the final-text block opened by `mark_text_block_start`."""
        return self._collapse_collapsible_block(collapsed, full)

    def _collapse_collapsible_block(self, collapsed: str, full: str) -> bool:
        """Shared by `collapse_thinking_block`/`collapse_text_block`; a no-op
        if no block was marked."""
        block = self._collapsible_block
        self._collapsible_block = None
        if block is None:
            return False
        return self._splice_collapsed_span(block.start, block.end, collapsed, full)

    def _mark_collapsible_block_start(self, kind: str) -> None:
        start = len(self._merged_output)
        self._collapsible_block = OpenCollapsibleBlock(start, start, kind)

    def update_shell_output(self, key: str, text: str) -> None:
        """Grow or replace `key`'s own live shell-output line with `text`.

        Mirrors `UIOutput.update_shell_output`; see `_update_keyed_line`.
        """
        self._update_keyed_line(self._shell_output_spans, key, text)

    def finish_shell_output(self, key: str, collapsed: str, full: str) -> bool:
        """Collapse `key`'s live line (opened via `update_shell_output`)
        into `collapsed`, registering it as Ctrl+O-expandable holding
        `full`. Uses this key's own tracked `end`, not
        `len(self._merged_output)` — see `UIOutput.finish_shell_output`
        for why.
        """
        span = self._shell_output_spans.pop(key, None)
        if span is None or not full:
            return False
        start, end = span
        source = CollapsibleBlockSource(stylize_muted(collapsed), stylize_muted(full))
        if not self._replace_span(start, end, source.collapsed):
            return False
        self._rendered_blocks.append([start, start + len(source.collapsed), source])
        return True

    def _splice_collapsed_span(
        self, start: int, end: int, collapsed: str, full: str
    ) -> bool:
        """Shared low-level mechanics for both the single-slot tracker
        (thinking/text) and the keyed one (shell output). `full` is the
        caller's own accumulated text — same "don't re-read the buffer"
        contract as `UIOutput`'s counterpart (a stray carriage return in a
        streamed delta can rewrite/erase part of the *rendered* text via
        `merge_output_chunk`, which this class also uses).
        """
        if not full or end <= start:
            return False
        source = CollapsibleBlockSource(stylize_muted(collapsed), stylize_muted(full))
        if not self._replace_span(start, end, source.collapsed):
            return False
        self._rendered_blocks.append([start, start + len(source.collapsed), source])
        return True

    def update_tool_prepare(self, key: str, text: str) -> None:
        """Print or update `key`'s own "Prepare tool parameters" line.

        See `_update_keyed_line` for the mechanics. Passing an empty
        `text` erases the line and stops tracking `key`.
        """
        self._update_keyed_line(self._tool_prepare_spans, key, text)

    def _update_keyed_line(
        self, spans: "dict[str, tuple[int, int]]", key: str, text: str
    ) -> None:
        """Shared mechanics for `update_tool_prepare`/`update_shell_output`.

        Mirrors `UIOutput._update_keyed_line`: replacing in place is what
        lets two keys' lines grow concurrently.
        """
        span = spans.get(key)
        if span is None:
            if not text:
                return
            start = len(self._merged_output)
            self.append_to_output(text, end="", kind="progress")
            spans[key] = (start, len(self._merged_output))
            return
        start, end = span
        styled = stylize_muted(text) if text else ""
        if not self._replace_span(start, end, styled):
            return
        if text:
            spans[key] = (start, start + len(styled))
        else:
            spans.pop(key, None)

    def toggle_collapsible_block_at_offset(self, offset: int) -> bool:
        """Expand/collapse the collapsible block at-or-before `offset`.

        Mirrors `UIOutput.toggle_collapsible_block_at_cursor`, but takes the
        offset explicitly — this class has no real cursor of its own; the
        caller (the sub-agent live view) supplies the shared output pane's
        cursor position. Returns whether a block was found and toggled.
        """
        target = None
        for block in self._rendered_blocks:
            if block[0] > offset:
                break
            target = block
        if target is None:
            return False
        source = target[2]
        new_expanded = not source.expanded
        new_text = source.full if new_expanded else source.collapsed
        if not self._replace_span(target[0], target[1], new_text):
            return False
        source.expanded = new_expanded
        target[1] = target[0] + len(new_text)
        return True

    @property
    def rendered_blocks(self) -> list:
        """[start, end, source] per tracked toggle block (public API)."""
        return self._rendered_blocks

    async def ask_user_choice(
        self, spec: ChoiceSpec, agent_id: str | None = None
    ) -> str:
        # No parent write to guard, so no lock (see `ask_user`).
        return await self._wrapped.ask_user_choice(
            spec, agent_id=agent_id if agent_id is not None else self._agent_id
        )

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        return await self._wrapped.run_interactive_command(cmd, shell)

    async def run_async(self) -> Any:
        return await self._wrapped.run_async()

    def accumulate_usage(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """Forward this sub-agent's token usage to the parent UI's session
        totals, so delegated runs count toward the displayed usage instead of
        being silently dropped. `context_usage` is deliberately NOT forwarded:
        it reports the *current context window's* occupancy, and this
        sub-agent's window is not the parent's — forwarding it would make the
        parent's context-window indicator show this sub-agent's size instead
        of its own.
        """
        accumulate = getattr(self._wrapped, "accumulate_usage", None)
        if accumulate is not None:
            accumulate(usage)

    def get_buffered_output(self) -> str:
        """Get all buffered output."""
        return self._merged_output

    def flush_to_parent(self) -> None:
        """Flush buffered output to parent UI."""
        output = self.get_buffered_output()
        if not output:
            return
        if self._prefix:
            output = "\n".join(
                f"{self._prefix}{line}" if line.strip() != "" else ""
                for line in output.split("\n")
            )
        self._wrapped.append_to_output(output)
        self._buffer.clear()

    def clear_buffer(self) -> None:
        """Clear the buffer without flushing."""
        self._buffer.clear()
        self._merged_output = ""
        self._rendered_blocks = []
        self._collapsible_block = None
        self._tool_prepare_spans = {}
        self._shell_output_spans = {}

    @property
    def yolo(self) -> bool | frozenset:
        """Delegate YOLO mode to the wrapped parent UI."""
        return self._wrapped.yolo

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ) -> None:
        """High-priority status messages (e.g. a tool-call notification mid
        sub-agent execution). Buffered like everything else — same
        destination as `append_to_output`.

        Deliberately not a bypass to the parent UI: routing status straight to
        main makes it visible sooner, at the cost of leaking routine
        sub-agent chatter (search queries, fetch status) into the main
        transcript. That chatter belongs in this sub-agent's own live view,
        which reads the buffer via `get_buffered_output()`.
        """
        self.append_to_output(
            *values, sep=sep, end=end, file=file, flush=flush, kind=kind
        )
