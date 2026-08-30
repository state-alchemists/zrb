import re
from typing import TYPE_CHECKING

from zrb.util.cli.ansi import strip_trailing_padding
from zrb.util.cli.latex_math import convert_math_to_unicode
from zrb.util.cli.mermaid_diagram import convert_mermaid_to_art

if TYPE_CHECKING:
    from rich.theme import Theme


def render_markdown(
    markdown_text: str, width: int | None = None, theme: "Theme | None" = None
) -> str:
    """
    Renders Markdown to a string, ensuring link URLs are visible.
    """
    # lazy: heavy third-party
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.theme import Theme

    from zrb.config.config import (
        CFG,  # lazy: zrb internal (heavy via transitive — CFG composes 15 mixins)
    )

    if CFG.LLM_UI_ENABLE_MARKDOWN_MATH:
        markdown_text = convert_math_to_unicode(markdown_text)
    if CFG.LLM_UI_ENABLE_MARKDOWN_MERMAID:
        markdown_text = convert_mermaid_to_art(markdown_text, width=width)

    if theme is None:
        theme = Theme(
            {
                "markdown.link": CFG.LLM_UI_STYLE_MARKDOWN_LINK,
                "markdown.link_url": CFG.LLM_UI_STYLE_MARKDOWN_LINK_URL,
                # Headers/code blocks are themeable too (see config/theme.py).
                "markdown.h1": CFG.LLM_UI_STYLE_MARKDOWN_H1,
                "markdown.code": CFG.LLM_UI_STYLE_MARKDOWN_CODE,
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

    return strip_trailing_padding(output)
