"""The web tools: open a page, search the internet, and the backends behind them."""

from zrb.llm.tool.web.tools import (
    convert_html_to_markdown,
    fetch_page_fallback,
    normalize_search_result,
    notify,
    open_web_page,
    run_blocking,
    search_internet,
)

__all__ = [
    "convert_html_to_markdown",
    "fetch_page_fallback",
    "normalize_search_result",
    "notify",
    "open_web_page",
    "run_blocking",
    "search_internet",
]
