def render_markdown(markdown_text: str) -> str:
    """
    Renders Markdown to a string, ensuring link URLs are visible.
    """
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    markdown = Markdown(markdown_text, hyperlinks=False)
    with console.capture() as capture:
        console.print(markdown)
    return capture.get()
