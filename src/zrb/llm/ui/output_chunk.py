"""Carriage-return-aware output merging and the collapsible-block value
object, shared by every UI that renders a live-updating output pane.

Used by `ui/default/output.py`'s `UIOutput` (the real terminal pane) and
`ui/buffered_ui.py`'s `BufferedUI` (the stand-in used for concurrent
sub-agents) — kept dependency-free (stdlib only, no `zrb.llm.*` imports) so
neither has to import the other's module to get it. Same rationale as
`zrb.llm.factory_resolver`.
"""

from __future__ import annotations

import re


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


class OpenCollapsibleBlock:
    """A live thinking or final-text block, from its mark to its collapse.

    Tracks its own `[start, end)` instead of claiming everything up to the
    buffer tail. A concurrent writer — a trigger line, a background task, a
    sub-agent's forwarded output — appends at the tail while the block is
    open, and "everything between my mark and the end" would swallow it. The
    keyed live lines (`update_shell_output`) learned this the same way.

    `kind` is the `append_to_output` kind whose chunks belong to this block:
    `"thinking"` or `"streaming"`, both unique to those two streams, so a
    concurrent writer's default `"text"` is never mistaken for block content.
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
    r"""`merge_output_chunk`, but keeping an open block's content contiguous.

        A chunk belonging to `block` is merged at the block's own `end` rather
        than the buffer tail, so anything a concurrent writer appended after the
        block stays outside it and survives the collapse. **Advances `block.end`
        in place** when it absorbs the chunk.

        Merging into `current_text[:block.end]` keeps ``
    `` handling honest:
        a status rewrite erases back to the block's own last line, never into a
        foreign line that happens to sit below it.

        Returns `(new_text, rebase_from)`. Absorbing a chunk rewrites the buffer
        *before* whatever a concurrent writer already put after the block, so
        every span tracked at or past `rebase_from` has moved and the caller must
        shift it — the same bookkeeping `replace_output_span` does for its own
        edits. `rebase_from` is `-1` for a plain tail append, which moves nothing.
    """
    if block is None or kind != block.kind or block.end > len(current_text):
        return merge_output_chunk(current_text, content), -1
    rebase_from = block.end
    head = merge_output_chunk(current_text[:rebase_from], content)
    tail = current_text[rebase_from:]
    block.end = len(head)
    return head + tail, rebase_from
