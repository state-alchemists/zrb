import io
import sys
from collections.abc import Sequence

Rows = Sequence[Sequence[str]]


def create_markdown_table(headers: Sequence[str], rows: Rows) -> str:
    """Raw GitHub-flavoured markdown; newlines in a cell become `<br>`."""

    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", "<br>")

    lines = [
        "| " + " | ".join(cell(h) for h in headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def render_table(headers: Sequence[str], rows: Rows) -> str:
    """The same table drawn by rich; colored only when stdout is a terminal."""
    from rich.console import Console  # lazy: heavy third-party deferral
    from rich.table import Table  # lazy: heavy third-party deferral

    table = Table(show_lines=True)
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*row)
    buffer = io.StringIO()
    Console(file=buffer, force_terminal=sys.stdout.isatty()).print(table)
    return buffer.getvalue().rstrip()
