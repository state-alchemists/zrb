from zrb.config.config import CFG


async def open_web_page(url: str) -> dict:
    """
    Downloads and converts a web page into clean, readable Markdown.

    **WHEN TO USE:**
    - To read specific articles, documentation, or blog posts.
    - To extract structured information from a known URL.

    **ARGS:**
    - `url`: The full web address to fetch.
    """
    try:
        html_content, links = await _fetch_page_content(url)
        markdown_content = _convert_html_to_markdown(html_content)
        return {"content": markdown_content, "links_on_page": links}
    except Exception as e:
        return {"error": f"Failed to fetch content from {url}: {str(e)}"}


async def search_internet(
    query: str,
    page: int = 1,
) -> dict:
    """
    Performs a broad internet search.

    **WHEN TO USE:**
    - When you need to find information but don't have a specific URL.

    **ARGS:**
    - `query`: The search string or question.
    - `page`: Result page number (default 1).
    """
    if (
        CFG.SEARCH_INTERNET_METHOD.strip().lower() == "serpapi"
        and CFG.SERPAPI_KEY != ""
    ):
        from zrb.llm.tool.search.serpapi import search_internet as serpapi_search

        return serpapi_search(query, page=page)
    if (
        CFG.SEARCH_INTERNET_METHOD.strip().lower() == "brave"
        and CFG.BRAVE_API_KEY != ""
    ):
        from zrb.llm.tool.search.brave import search_internet as brave_search

        return brave_search(query, page=page)
    from zrb.llm.tool.search.searxng import search_internet as searxng_search

    return searxng_search(query, page=page)


async def _fetch_page_content(url: str) -> tuple:
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": user_agent})
            await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.content()
            links = await page.eval_on_selector_all(
                "a[href]",
                "(elements, baseUrl) => elements.map(el => { const href = el.getAttribute('href'); if (!href || href.startsWith('#')) return null; try { return new URL(href, baseUrl).href; } catch (e) { return null; } }).filter(href => href !== null)",
                url,
            )
            await browser.close()
            return content, links
    except Exception:
        from urllib.parse import urljoin

        import requests
        from bs4 import BeautifulSoup

        response = requests.get(url, headers={"User-Agent": user_agent})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        links = [
            urljoin(url, a["href"])
            for a in soup.find_all("a", href=True)
            if not a["href"].startswith("#")
        ]
        return response.text, links


def _convert_html_to_markdown(html_text: str) -> str:
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md

    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(
        ["script", "link", "meta", "style", "header", "footer", "nav", "aside"]
    ):
        tag.decompose()
    return md(str(soup))
