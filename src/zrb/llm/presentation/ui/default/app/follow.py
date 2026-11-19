"""Whether the transcript keeps following the newest output.

The pane pins its view to the cursor, so "following" means "the cursor is on the
last line". The append path can read that for itself: it moves the cursor when it
was at the tail and leaves it alone when it was not. The refresh loop cannot,
because it repaints after the text has already grown, when both answers look
alike. This keeps the answer from *before* the growth, and the wheel and the
paging keys write it back when the reader moves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prompt_toolkit.widgets import TextArea


class OutputFollow:
    """What the refresh loop asks before it pulls the view to the bottom."""

    def __init__(self, following: bool = True) -> None:
        self.following = following

    def note(self, text_area: "TextArea") -> None:
        """Remember whether *text_area* is on its last line."""
        self.following = is_at_last_line(text_area)

    def resume(self) -> None:
        """Follow again: a submitted message puts the reader back on the tail."""
        self.following = True


def is_at_last_line(text_area: "TextArea") -> bool:
    """Whether nothing follows the cursor, read off the raw string.

    The same test the append path uses: `cursor_position_row` would build a line
    index, an O(buffer) scan, and this runs on every streamed chunk.
    """
    return text_area.text.find("\n", text_area.buffer.cursor_position) == -1
