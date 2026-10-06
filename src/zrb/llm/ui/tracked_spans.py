"""Offset bookkeeping for the in-place-rewritten spans of an output buffer.

Shared by `UIOutput` and `BufferedUI`; keeps the open block and keyed live
lines valid across a splice.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from zrb.llm.ui.output_chunk import (
    CollapsibleBlockSource,
    OpenCollapsibleBlock,
    rebase_tracked_spans,
)
from zrb.util.cli.style import stylize_muted


class TrackedSpans:
    """The open collapsible block plus the keyed live lines of one buffer.

    The owner supplies its buffer through callables: `get_text`/`set_text`
    read and write the whole text, `get_blocks` returns its `rendered_blocks`
    list (`[start, end, source, ...]` per entry, position-ordered),
    `register_block` records a newly collapsed span there, and `append`
    appends a fresh keyed line at the tail with the owner's progress styling.
    """

    def __init__(
        self,
        get_text: Callable[[], str],
        set_text: Callable[[str], None],
        get_blocks: Callable[[], list[list[Any]]],
        register_block: Callable[[int, int, CollapsibleBlockSource], None],
        append: Callable[[str], None],
    ) -> None:
        self._get_text = get_text
        self._set_text = set_text
        self._get_blocks = get_blocks
        self._register_block = register_block
        self._append = append
        # One slot suffices: thinking and final text never stream at once.
        self.open_block: OpenCollapsibleBlock | None = None
        # Keyed so concurrent tool calls / shell commands each grow their own line.
        self._tool_prepare_spans: dict[str, tuple[int, int]] = {}
        self._shell_output_spans: dict[str, tuple[int, int]] = {}

    def reset(self) -> None:
        """Forget every tracked offset (the buffer was cleared)."""
        self.open_block = None
        self._tool_prepare_spans = {}
        self._shell_output_spans = {}

    def replace(self, start: int, end: int, replacement: str) -> bool:
        """Replace ``text[start:end]`` with `replacement`, shifting every
        tracked offset (open block included) past the span by the length delta.

        Returns ``False`` when the span no longer exists.
        """
        text = self._get_text()
        if end > len(text):
            return False
        delta = len(replacement) - (end - start)
        new_text = text[:start] + replacement + text[end:]
        self.shift(end, delta)
        self._set_text(new_text)
        return True

    def shift(self, after: int, delta: int) -> None:
        """`rebase`, moving the open block too: for any edit other than the
        open block growing."""
        self.rebase(after, delta)
        block = self.open_block
        if delta and block is not None and block.start >= after:
            block.start += delta
            block.end += delta

    def rebase(self, after: int, delta: int) -> None:
        """Shift every tracked offset at or past `after` by `delta`.

        The open block is not shifted: on the insert path it is that block
        growing, and `merge_into_block` already advanced its `end`. Use
        `shift` for any other edit.
        """
        rebase_tracked_spans(
            self._get_blocks(),
            (self._tool_prepare_spans, self._shell_output_spans),
            after,
            delta,
        )

    def mark_block_start(self, kind: str) -> None:
        """Open a thinking (`"thinking"`) or final-text (`"streaming"`) block
        at the current tail."""
        start = len(self._get_text())
        self.open_block = OpenCollapsibleBlock(start, start, kind)

    def collapse_block(self, collapsed: str, full: str) -> bool:
        """Collapse the block opened by `mark_block_start`; no-op if none."""
        block = self.open_block
        self.open_block = None
        if block is None:
            return False
        return self._splice_collapsed_span(block.start, block.end, collapsed, full)

    def update_tool_prepare(self, key: str, text: str) -> None:
        """Grow or replace `key`'s own "Prepare tool parameters" line."""
        self._update_keyed_line(self._tool_prepare_spans, key, text)

    def update_shell_output(self, key: str, text: str) -> None:
        """Grow or replace `key`'s own live shell-output line with `text`
        (the full accumulated stdout+stderr echo so far)."""
        self._update_keyed_line(self._shell_output_spans, key, text)

    def finish_shell_output(self, key: str, collapsed: str, full: str) -> bool:
        """Collapse `key`'s live line into `collapsed`, registered as
        Ctrl+O-expandable holding `full`.

        Uses this key's tracked `end`, not the buffer length: other keys'
        lines may have grown past it.
        """
        span = self._shell_output_spans.pop(key, None)
        if span is None:
            return False
        return self._splice_collapsed_span(*span, collapsed, full)

    def _splice_collapsed_span(
        self, start: int, end: int, collapsed: str, full: str
    ) -> bool:
        """Splice `collapsed` over `[start, end)` and register the span as
        Ctrl+O-expandable.

        `full` is the caller's accumulated text, not re-read from the buffer:
        a stray `\\r` in a streamed chunk can erase part of the *rendered*
        line. A no-op if nothing was accumulated.
        """
        if not full or end <= start:
            return False
        source = CollapsibleBlockSource(stylize_muted(collapsed), stylize_muted(full))
        if not self.replace(start, end, source.collapsed):
            return False
        self._register_block(start, start + len(source.collapsed), source)
        return True

    def _update_keyed_line(
        self, spans: dict[str, tuple[int, int]], key: str, text: str
    ) -> None:
        """Grow or replace `key`'s own tracked span in `spans` with `text`.

        The first call appends; later calls replace exactly that span. An
        empty `text` erases the line and stops tracking `key`.
        """
        span = spans.get(key)
        if span is None:
            if not text:
                return
            start = len(self._get_text())
            self._append(text)
            spans[key] = (start, len(self._get_text()))
            return
        start, end = span
        styled = stylize_muted(text) if text else ""
        if not self.replace(start, end, styled):
            return
        if text:
            spans[key] = (start, start + len(styled))
        else:
            spans.pop(key, None)

    def toggle_at(self, offset: int) -> bool:
        """Expand/collapse the last collapsible block at-or-before `offset`.

        Returns whether a block was found and toggled.
        """
        target = None
        for block in self._get_blocks():
            if block[0] > offset:
                break
            if isinstance(block[2], CollapsibleBlockSource):
                target = block
        if target is None:
            return False
        source = target[2]
        new_expanded = not source.expanded
        new_text = source.full if new_expanded else source.collapsed
        if not self.replace(target[0], target[1], new_text):
            return False
        source.expanded = new_expanded
        target[1] = target[0] + len(new_text)
        return True
