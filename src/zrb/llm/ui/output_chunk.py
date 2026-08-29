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
