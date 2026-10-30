"""Geometry for a panel that docks into the layout instead of floating over it.

A `Float` covers the transcript: whatever is underneath cannot be read, and
while the panel holds the focus it cannot even be scrolled. A docked panel takes
its rows out of the transcript instead, so what it may take has to be a share of
the screen rather than however many rows its content happens to need.

Two of the three panels render through a `FormattedTextControl`, which cannot
scroll the way a `Buffer` does: the rows it returns *are* the whole window. So
the cap is applied by painting only a slice of rows, and `RowWindow` keeps that
slice on the row the cursor is on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import OneStyleAndTextTuple, StyleAndTextTuples
    from prompt_toolkit.layout.dimension import Dimension

# One painted row ends with this; a row of fragments is joined by appending it.
_ROW_BREAK: "OneStyleAndTextTuple" = ("", "\n")

PANEL_MIN_ROWS = 4
"""Rows a panel shows, below which it is a title bar with nothing under it."""

PANEL_SCREEN_DIVISOR = 3
"""A panel may take a third of the screen; the transcript keeps the rest."""

FRAME_ROWS = 2
"""Rows a `Frame` spends on its border, one above its content and one below."""

LAYOUT_MIN_ROWS = 16
"""Rows the rest of the layout keeps for itself before a panel gets any.

The title bar (2), the info bar (3), both spacers (2), the input frame (3), the
hint line (1), the status bar (1) and one row of transcript: thirteen rows
before a panel is considered. A docked panel's own `Frame` then spends
`FRAME_ROWS` (2) on its border, so the thirteen plus that border is fifteen — the
sixteenth row is the slack that keeps a one-row panel from asking for a screen
exactly as tall as itself. A panel that asks for more than `rows -
LAYOUT_MIN_ROWS` asks for a screen that does not exist, and prompt_toolkit paints
its "window too small" note instead of the layout, so the cap yields rather than
insists. A layout change that adds or drops a bar has to move this number with
it.
"""


def terminal_row_count(ui: object) -> int:
    """Terminal rows, read from the running application first.

    Its output is a dup of the real stdout, while `get_terminal_size` may read a
    redirected fd and disagree with what the renderer is painting.
    """
    app = _running_application(ui)
    if app is not None:
        try:
            return app.output.get_size().rows
        except (AttributeError, OSError, ValueError):
            # A redirected or console-less output: fall through to the
            # terminal probe, the same fallback `output_field_width` uses.
            pass
    return get_terminal_size().lines


def panel_row_cap(ui: object) -> int:
    """Rows of content a docked panel may paint on this terminal.

    A third of the screen, never fewer than `PANEL_MIN_ROWS` while the layout
    can spare them, and never more than the layout can spare at all.
    """
    rows = terminal_row_count(ui)
    share = max(PANEL_MIN_ROWS, rows // PANEL_SCREEN_DIVISOR)
    return max(0, min(share, rows - LAYOUT_MIN_ROWS))


def framed_panel_height(content_rows) -> "Callable[[], Dimension]":
    """A `Frame` height that gives a docked panel exactly `content_rows()` rows.

    Exact rather than merely preferred: the height is what the cap promised, so
    the panel neither grows with its content nor bargains with the transcript
    for rows. Returns a callable because the content changes between renders.
    """
    return _exact_height(lambda: content_rows() + FRAME_ROWS)


def panel_content_height(content_rows) -> "Callable[[], Dimension]":
    """A height for a panel's own content window, border excluded.

    A `TextArea` draws no `Frame` of its own, so its rows are the content's.
    """
    return _exact_height(content_rows)


def _exact_height(rows) -> "Callable[[], Dimension]":
    """An exact height, re-read on every render: `rows()` changes as data lands."""

    def height() -> "Dimension":
        # lazy: heavy third-party
        from prompt_toolkit.layout.dimension import Dimension

        return Dimension.exact(rows())

    return height


def rendered_row_count(frags: "StyleAndTextTuples") -> int:
    """How many terminal rows *frags* paint."""
    return len(_split_rows(frags))


class RowWindow:
    """A fixed-height window over rendered rows, kept on an anchor row.

    The offset follows the cursor: a row that scrolls past the bottom pulls the
    window down (or up) until it is inside again, so a 20-option question never
    hides the option the user is on.
    """

    def __init__(self) -> None:
        self._first_row = 0

    def reset(self) -> None:
        """Start a new panel at the top."""
        self._first_row = 0

    def slice(
        self,
        frags: "StyleAndTextTuples",
        anchor: int,
        rows: int,
        footer: int = 0,
    ) -> "StyleAndTextTuples":
        """At most *rows* rows of *frags*, with row *anchor* among them.

        The last *footer* rows stay painted whatever the window does: they are
        the key hint, and a legend the user cannot see is not a legend. One body
        row always survives, so the anchor is never the thing that gets dropped.
        """
        lines = _split_rows(frags)
        total = len(lines)
        rows = max(0, min(rows, total))
        if rows == 0:
            return []
        footer = max(0, min(footer, rows - 1, total))
        body_rows = rows - footer
        body_total = total - footer
        if body_rows <= 0:
            return _join_rows(lines[body_total:])
        first = self._follow(min(anchor, body_total - 1), body_rows, body_total)
        self._first_row = first
        return _join_rows(lines[first : first + body_rows] + lines[body_total:])

    def _follow(self, anchor: int, rows: int, total: int) -> int:
        """The first visible row, moved just enough to keep *anchor* in view."""
        if total <= rows:
            return 0
        # Above the window pulls it up; below pushes it down. Either way the
        # anchor ends up on the last (or first) visible row, never outside.
        first = min(self._first_row, anchor)
        first = max(first, anchor - rows + 1)
        return max(0, min(first, total - rows))


def _split_rows(frags: "StyleAndTextTuples") -> list["StyleAndTextTuples"]:
    """*frags* as one fragment list per painted row."""
    rows: list["StyleAndTextTuples"] = []
    if not frags:
        return rows
    rows.append([])
    for fragment in frags:
        style, text = fragment[0], fragment[1]
        for index, piece in enumerate(text.split("\n")):
            if index:
                rows.append([])
            if piece:
                rows[-1].append((style, piece))
    if len(rows) > 1 and not rows[-1]:
        # A trailing newline ends the last row; it does not open an empty one.
        rows.pop()
    return rows


def _join_rows(rows: list["StyleAndTextTuples"]) -> "StyleAndTextTuples":
    """The fragment list that paints *rows*, one row per line."""
    frags: "StyleAndTextTuples" = []
    for row in rows:
        frags += row
        frags.append(_ROW_BREAK)
    return frags


def _running_application(ui: object):
    """The live prompt_toolkit application, or None before it is built."""
    if not getattr(ui, "is_application_built", False):
        return None
    return getattr(ui, "application", None)
