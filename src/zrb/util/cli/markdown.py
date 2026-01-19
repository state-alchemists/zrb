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
                "markdown.code": "bold white on #333333",
            }
        )

    console = Console(width=width, theme=theme, force_terminal=True)
    markdown = Markdown(markdown_text, hyperlinks=False)
    with console.capture() as capture:
        console.print(markdown)
    return capture.get()
