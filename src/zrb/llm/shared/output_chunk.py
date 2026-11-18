"""Carriage-return-aware output merging and collapsible-block value objects.

Shared by `UIOutput` and `BufferedUI`; stdlib-only so neither imports the other.
"""

from __future__ import annotations

import re
from typing import Any


def merge_output_chunk(current_text: str, content: str) -> str:
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


def rebase_tracked_spans(
    rendered_blocks: list[list[Any]],
    span_maps: tuple[dict[str, tuple[int, int]], ...],
    after: int,
    delta: int,
) -> None:
    """Shift every rendered block and keyed span starting at or past `after`
    by `delta`, in place."""
    if not delta:
        return
    for entry in rendered_blocks:
        if entry[0] >= after:
            entry[0] += delta
            entry[1] += delta
    for spans in span_maps:
        for key, (span_start, span_end) in list(spans.items()):
            if span_start >= after:
                spans[key] = (span_start + delta, span_end + delta)


class CollapsibleBlockSource:
    """Rendered-block payload for a collapsible line (tool-call/result,
    thinking, ...)."""

    __slots__ = ("collapsed", "full", "expanded")

    def __init__(self, collapsed: str, full: str):
        self.collapsed = collapsed
        self.full = full
        self.expanded = False


class OpenCollapsibleBlock:
    """A live thinking or final-text block, from its mark to its collapse.

    Tracks its own `[start, end)` so a concurrent writer appending at the
    tail is not swallowed. `kind` (`"thinking"` or `"streaming"`) is the
    `append_to_output` kind whose chunks belong to this block.
    """

    __slots__ = ("start", "end", "kind")

    def __init__(self, start: int, end: int, kind: str):
        self.start = start
        self.end = end
        self.kind = kind


def merge_into_block(
    current_text: str,
    content: str,
    block: OpenCollapsibleBlock | None,
    kind: str,
) -> tuple[str, int]:
    """`merge_output_chunk`, but keeping an open block's content contiguous.

    A chunk of `block`'s kind merges at the block's own `end`, not the buffer
    tail, so a concurrent writer's later line stays outside the block; a
    ``\\r`` rewrite never erases into that foreign line. Advances
    `block.end` in place.

    Returns `(new_text, rebase_from)`: spans at or past `rebase_from` moved
    and the caller must shift them; `-1` for a plain tail append.
    """
    if block is None or kind != block.kind or block.end > len(current_text):
        return merge_output_chunk(current_text, content), -1
    rebase_from = block.end
    head = merge_output_chunk(current_text[:rebase_from], content)
    tail = current_text[rebase_from:]
    block.end = len(head)
    return head + tail, rebase_from
