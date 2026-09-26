"""Offset bookkeeping for the live, in-place-rewritten spans of an output buffer.

Shared by the two outputs that rewrite their transcript somewhere other than
the tail: `UIOutput` (the default UI's prompt_toolkit buffer) and `BufferedUI`
(a sub-agent's accumulating string). Each owns where its text lives and how a
Ctrl+O-expandable block is registered; this part owns the offsets into that
text — the open thinking/final-text block, the keyed tool-prepare and
shell-output lines — and keeps every one of them valid across a splice.
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
        # Set by mark_block_start; consumed by collapse_block. One slot
        # suffices: thinking and final text never stream at the same time.
        self.open_block: OpenCollapsibleBlock | None = None
        # Keyed rather than a single slot so concurrent tool calls / shell
        # commands each grow their own line — see _update_keyed_line.
        self._tool_prepare_spans: dict[str, tuple[int, int]] = {}
        self._shell_output_spans: dict[str, tuple[int, int]] = {}

    def reset(self) -> None:
        """Forget every tracked offset (the buffer was cleared)."""
        self.open_block = None
        self._tool_prepare_spans = {}
        self._shell_output_spans = {}

    def replace(self, start: int, end: int, replacement: str) -> bool:
        """Replace ``text[start:end]`` with `replacement`, shifting every
        tracked offset past the span by the length delta.

        Rendered blocks and other keys' spans get the shift — one key's span
        growing/shrinking/resolving must not invalidate another's still-open
        span. So does the open collapsible block: a shell line growing below
        an open thinking block would otherwise leave the mark pointing
        mid-line, and the collapse would splice over the tail of that line.
        Returns ``False`` when the span no longer exists (the buffer was
        rewritten or never received the text).
        """
        text = self._get_text()
        if end > len(text):
            return False
        delta = len(replacement) - (end - start)
        new_text = text[:start] + replacement + text[end:]
        self.rebase(end, delta)
        block = self.open_block
        if delta and block is not None and block.start >= end:
            # A foreign edit above an open block moves the whole block.
            block.start += delta
            block.end += delta
        self._set_text(new_text)
        return True

    def rebase(self, after: int, delta: int) -> None:
        """Shift every tracked offset at or past `after` by `delta`.

        Shared by every path that rewrites the buffer somewhere other than the
        tail — `replace` and the collapsible-block insert in the owner's
        `append_to_output`. An offset left behind points into the wrong text,
        and the next write through it lands inside somebody else's content.

        The open collapsible block is deliberately NOT shifted here: the
        insert path is that block growing, and `merge_into_block` has already
        advanced its `end`. A foreign edit that does move it shifts it itself,
        in `replace`.
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
        """Collapse the block opened by `mark_block_start`.

        See `_splice_collapsed_span` for why `full` must be the caller's own
        accumulated text. A no-op if no block was marked (e.g. this UI missed
        the start signal).
        """
        block = self.open_block
        self.open_block = None
        if block is None:
            return False
        return self._splice_collapsed_span(block.start, block.end, collapsed, full)

    def update_tool_prepare(self, key: str, text: str) -> None:
        """Grow or replace `key`'s own "Prepare tool parameters" line.

        Never a rendered block: this line needs no Ctrl+O expansion.
        """
        self._update_keyed_line(self._tool_prepare_spans, key, text)

    def update_shell_output(self, key: str, text: str) -> None:
        """Grow or replace `key`'s own live shell-output line with `text`
        (the full accumulated stdout+stderr echo so far).

        The first attempt at this feature marked one offset and let two
        concurrently-running Shell commands' echo interleave between mark and
        collapse — whichever collapsed first devoured the other's lines too.
        Replacing this key's own span wholesale on every update, never
        touching anything outside it, is what makes that interleave safe.
        """
        self._update_keyed_line(self._shell_output_spans, key, text)

    def finish_shell_output(self, key: str, collapsed: str, full: str) -> bool:
        """Collapse `key`'s live line into `collapsed`, registered as
        Ctrl+O-expandable holding `full`.

        Uses this key's own tracked `end`, not the buffer length: other keys'
        live lines may already have grown past this one by the time it
        finishes.
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

        The first call for a `key` appends `text` fresh (auto-styled as
        progress) and starts tracking its span; every later call replaces
        exactly that span (re-styled here, since `replace` applies no
        styling) — never anything else. That is what makes two keys' lines
        safe to grow concurrently. An empty `text` erases the line and stops
        tracking `key`.
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

        `rendered_blocks` is position-ordered, so this is "the block I'm
        looking at," or the most recent one when the cursor follows the tail.
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
