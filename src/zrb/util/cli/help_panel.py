"""Width-aware rendering of the TUI help panel (ASCII art + command tables).

The panel is re-rendered from this data on every terminal resize, so no *row*
is ever clipped to fit: a description wraps inside its column instead, and the
art keeps its own column until the remaining width stops being usable, at which
point it moves above the tables rather than being dropped. Row *count* is
capped separately (`max_commands`), which is a choice about screen real estate
rather than a consequence of the width.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zrb.util.cli.ansi import strip_trailing_padding

if TYPE_CHECKING:
    from rich.console import RenderableType

# Below this many columns for the command tables, the art stops sharing a row
# with them and is printed above instead.
MIN_CONTENT_WIDTH = 44

# Gap between the art column and the tables beside it.
_SIDE_BY_SIDE_OVERHEAD = 4


@dataclass
class HelpPanel:
    """The content of the help panel, independent of any terminal width."""

    commands: list[tuple[str, str]] = field(default_factory=list)
    shortcuts: list[tuple[str, str]] = field(default_factory=list)
    art: str = ""
    header: str = ""
    # Rows past this many are summarized as "... and N more" instead of
    # filling the screen. `None` lists every command.
    max_commands: int | None = None


def render_help_panel(panel: HelpPanel, width: int | None = None) -> str:
    """Render `panel` to an ANSI string that fits in `width` columns."""
    # lazy: heavy third-party
    from rich.console import Console, Group
    from rich.text import Text

    content = _build_content(panel)
    art = panel.art.strip("\n")
    if art != "" and not _fits_side_by_side(art, width):
        # Cropped rather than wrapped: re-flowing art lines would scramble the
        # picture, while a clipped edge still reads as the same picture.
        stacked_art = Text.from_ansi(art, no_wrap=True, overflow="crop")
        renderable: "RenderableType" = Group(stacked_art, Text(""), content)
    elif art != "":
        renderable = _build_side_by_side(art, content)
    else:
        renderable = content

    console = Console(width=width, force_terminal=True)
    with console.capture() as capture:
        console.print(renderable)
    return strip_trailing_padding(capture.get())


def _build_content(panel: HelpPanel) -> "RenderableType":
    """Header text plus one table per help section, stacked vertically."""
    # lazy: heavy third-party
    from rich.console import Group
    from rich.text import Text

    parts: list["RenderableType"] = []
    if panel.header.strip() != "":
        parts.extend([Text.from_ansi(panel.header.strip("\n")), Text("")])
    if panel.commands:
        rows = _cap_rows(panel.commands, panel.max_commands)
        parts.append(_build_table("Available Commands:", "Command", rows))
    if panel.shortcuts:
        if parts:
            parts.append(Text(""))
        parts.append(_build_table("Keyboard Shortcuts:", "Key", panel.shortcuts))
    return Group(*parts)


def _cap_rows(
    rows: list[tuple[str, str]], limit: int | None
) -> list[tuple[str, str]]:
    """Keep the first `limit` rows, summarizing the remainder in one row."""
    if limit is None or len(rows) <= limit:
        return rows
    return rows[:limit] + [("...", f"and {len(rows) - limit} more")]


def _build_table(
    title: str, key_header: str, rows: list[tuple[str, str]]
) -> "RenderableType":
    """A titled two-column table whose description column folds, never clips."""
    # lazy: heavy third-party
    from rich.console import Group
    from rich.table import Table
    from rich.text import Text

    table = Table(
        box=None,
        header_style="bold",
        expand=True,
        show_edge=False,
        pad_edge=False,
        padding=(0, 2),
    )
    table.add_column(key_header, no_wrap=True, style="bold")
    table.add_column("Description", overflow="fold")
    for key, description in rows:
        table.add_row(key, description)
    return Group(Text(title, style="bold"), table)


def _build_side_by_side(art: str, content: "RenderableType") -> "RenderableType":
    """One borderless row: the art in column 1, the tables beside it."""
    # lazy: heavy third-party
    from rich.table import Table
    from rich.text import Text

    outer = Table(
        box=None,
        show_header=False,
        expand=True,
        show_edge=False,
        pad_edge=False,
        padding=(0, 2),
    )
    # The art is a single tall cell, so a wrapping description below it can
    # never push art lines apart the way a shared row grid would.
    outer.add_column(no_wrap=True, overflow="crop", vertical="middle")
    outer.add_column(overflow="fold")
    outer.add_row(Text.from_ansi(art), content)
    return outer


def _fits_side_by_side(art: str, width: int | None) -> bool:
    if width is None:
        return True
    return width - get_art_width(art) - _SIDE_BY_SIDE_OVERHEAD >= MIN_CONTENT_WIDTH


def get_art_width(art: str) -> int:
    """Widest visible line of `art`, in terminal cells."""
    # lazy: heavy third-party
    from rich.text import Text

    return max(
        (Text.from_ansi(line).cell_len for line in art.splitlines()),
        default=0,
    )
