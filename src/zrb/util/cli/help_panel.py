"""Width-aware rendering of the TUI help panel (ASCII art + command table).

The panel is re-rendered from this data on every terminal resize, so no *row*
is ever clipped to fit: a description wraps inside its column instead, and the
art keeps its own column until the remaining width stops being usable, at which
point it moves above the table rather than being dropped. Row *count* is
capped separately (`max_commands`), which is a choice about screen real estate
rather than a consequence of the width.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zrb.util.cli.ansi import strip_trailing_padding

if TYPE_CHECKING:
    from rich.console import RenderableType

# Below this many columns for the command table, the art stops sharing a row
# with it and is printed above instead.
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
    """Header text plus a single table holding every help section."""
    # lazy: heavy third-party
    from rich.console import Group
    from rich.text import Text

    parts: list["RenderableType"] = []
    if panel.header.strip() != "":
        parts.extend([Text.from_ansi(panel.header.strip("\n")), Text("")])
    sections = _build_sections(panel)
    if sections:
        parts.append(_build_table(sections))
    return Group(*parts)


def _build_sections(panel: HelpPanel) -> list[tuple[str, list[tuple[str, str]]]]:
    """The non-empty help sections, each a caption plus its rows."""
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    if panel.commands:
        rows = _cap_rows(panel.commands, panel.max_commands)
        sections.append(("Available Commands:", rows))
    if panel.shortcuts:
        sections.append(("Keyboard Shortcuts:", list(panel.shortcuts)))
    return sections


def _cap_rows(rows: list[tuple[str, str]], limit: int | None) -> list[tuple[str, str]]:
    """Keep the first `limit` rows, summarizing the remainder in one row."""
    if limit is None or len(rows) <= limit:
        return rows
    return rows[:limit] + [("...", f"and {len(rows) - limit} more")]


def _build_table(sections: list[tuple[str, list[tuple[str, str]]]]) -> "RenderableType":
    """One table for every section, keys sharing a single column.

    A section caption spans the full width, so it cannot live in a column of
    its own: rich has no column-spanning cell, and a caption placed in the key
    column is cropped to that column's width. Each key/description pair is
    therefore a nested grid inside one full-width column, which is what lets
    the caption run edge to edge while every section's keys still line up --
    the grids share an explicitly measured key width instead of each table
    sizing its own.
    """
    # lazy: heavy third-party
    from rich.table import Table
    from rich.text import Text

    key_width = _key_column_width(sections)
    table = Table(
        box=None,
        show_header=False,
        expand=True,
        show_edge=False,
        pad_edge=False,
        padding=0,
    )
    table.add_column(overflow="fold")
    for index, (caption, rows) in enumerate(sections):
        if index > 0:
            table.add_row("")
        table.add_row(Text(caption, style="bold"))
        for key, description in rows:
            table.add_row(_build_row(key, description, key_width))
    return table


def _build_row(key: str, description: str, key_width: int) -> "RenderableType":
    """One key/description pair, laid out to a fixed key column."""
    # lazy: heavy third-party
    from rich.table import Table
    from rich.text import Text

    row = Table.grid(expand=True, padding=(0, 2))
    row.add_column(width=key_width, no_wrap=True)
    # `ratio` sends every spare column to the description; without it a short
    # description lets the key column absorb the slack and rows stop aligning.
    row.add_column(overflow="fold", ratio=1)
    # Bold on the cell, not the column: a column style also paints the padding
    # and the blank continuation lines of a wrapped description.
    row.add_row(Text(key, style="bold"), description)
    return row


def _key_column_width(sections: list[tuple[str, list[tuple[str, str]]]]) -> int:
    """Cells needed by the widest key across every section."""
    # lazy: heavy third-party
    from rich.text import Text

    return max(
        (Text.from_ansi(key).cell_len for _, rows in sections for key, _ in rows),
        default=0,
    )


def _build_side_by_side(art: str, content: "RenderableType") -> "RenderableType":
    """One borderless row: the art in column 1, the table beside it."""
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
