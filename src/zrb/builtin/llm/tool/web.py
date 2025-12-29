from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin

from zrb.builtin.llm.tool.search import brave, searxng, serpapi
from zrb.config.config import CFG
from zrb.config.llm_config import llm_config

_DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa


async def open_web_page(url: str) -> dict[str, Any]:
    """
    Fetches, parses, and converts a web page to readable Markdown.
    Preserves semantic structure, removes non-essentials, and extracts all absolute links.

    **EFFICIENCY TIP:**
    Use this tool to read the full content of a specific search result or article.
    It returns clean Markdown and a list of links, which is perfect for deep-diving
    into a topic without navigating a browser UI.

    Example:
    open_web_page(url='https://www.example.com/article')

    Args:
        url (str): The full URL of the web page.

    Returns:
        dict: Markdown content and a list of absolute links.
    """
    html_content, links = await _fetch_page_content(url)
    markdown_content = _convert_html_to_markdown(html_content)
    return {"content": markdown_content, "links_on_page": links}


def create_search_internet_tool() -> Callable:
    if llm_config.default_search_internet_tool is not None:
        return llm_config.default_search_internet_tool
    if (
        CFG.SEARCH_INTERNET_METHOD.strip().lower() == "serpapi"
        and CFG.SERPAPI_KEY != ""
    ):
        return serpapi.search_internet
    if (
        CFG.SEARCH_INTERNET_METHOD.strip().lower() == "brave"
        and CFG.BRAVE_API_KEY != ""
    ):
        return brave.search_internet
    return searxng.search_internet


async def _fetch_page_content(url: str) -> tuple[str, list[str]]:
    """Fetches the HTML content and all absolute links from a URL."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": _DEFAULT_USER_AGENT})
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_load_state("domcontentloaded")
                content = await page.content()
                links = await page.eval_on_selector_all(
                    "a[href]",
                    """
                    (elements, baseUrl) => elements.map(el => {
                        const href = el.getAttribute('href');
                        if (!href || href.startsWith('#')) return null;
                        try {
                            return new URL(href, baseUrl).href;
                        } catch (e) {
                            return null;
                        }
                    }).filter(href => href !== null)
                    """,
                    url,
                )
                return content, links
                # return json.dumps({"content": content, "links": links})
            finally:
                await browser.close()
    except Exception:
        import requests
        from bs4 import BeautifulSoup

        response = requests.get(url, headers={"User-Agent": _DEFAULT_USER_AGENT})
        if response.status_code != 200:
            raise Exception(
                f"Unable to retrieve page content. Status code: {response.status_code}"
            )
        content = response.text
        soup = BeautifulSoup(content, "html.parser")
        links = [
            urljoin(url, a["href"])
            for a in soup.find_all("a", href=True)
            if not a["href"].startswith("#")
        ]
        return content, links
        # return json.dumps({"content": content, "links": links})


def _convert_html_to_markdown(html_text: str) -> str:
    """Converts HTML content to a clean Markdown representation."""
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md

    soup = BeautifulSoup(html_text, "html.parser")
    # Remove non-content tags
    for tag in soup(
        ["script", "link", "meta", "style", "header", "footer", "nav", "aside"]
    ):
        tag.decompose()
    # Convert the cleaned HTML to Markdown
    return md(str(soup))
