import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.theme import Theme


def render_markdown(
    markdown_text: str, width: int | None = None, theme: "Theme | None" = None
) -> str:
    """
    Renders Markdown to a string, ensuring link URLs are visible.
    """
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.theme import Theme

    if theme is None:
        theme = Theme(
            {
                "markdown.link": "bold bright_cyan underline",
                "markdown.link_url": "italic bright_cyan underline",
                # Optional: You can customize headers or code blocks here too
                "markdown.h1": "bold magenta",
                "markdown.code": "bold white",
            }
        )

    console = Console(width=width, theme=theme, force_terminal=True)
    markdown = Markdown(markdown_text, hyperlinks=False)
    with console.capture() as capture:
        console.print(markdown)

    output = capture.get()
    # Strip RGB background colors (e.g., 48;2;39;40;34) to ensure transparency
    # Matches ;48;2;... or [48;2;...
    output = re.sub(r"(?:(?<=\[)|;)48;2;\d+;\d+;\d+", "", output)

    # Remove Rich's padding spaces from each line, handling ANSI codes
    # Simple rstrip() fails if the line ends with ANSI codes (e.g., reset)
    def _strip_ansi_aware(line: str) -> str:
        # Match trailing sequence of spaces and ANSI codes
        match = re.search(r"((?:\s|\x1b\[[0-9;]*m)+)$", line)
        if match:
            tail = match.group(1)
            # Remove spaces from the tail
            clean_tail = re.sub(r"\s+", "", tail)
            return line[: match.start(1)] + clean_tail
        return line

    output = "\n".join(_strip_ansi_aware(line) for line in output.splitlines())
    return output
