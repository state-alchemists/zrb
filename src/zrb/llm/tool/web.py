import json

from zrb.config.config import CFG
from zrb.llm.agent import create_agent, run_agent
from zrb.llm.config.config import llm_config
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.prompt.prompt import get_web_summarizer_system_prompt


async def open_web_page(url: str, summarize: bool = True) -> dict:
    """
    Downloads and converts a web page into Markdown.

    **RESEARCH MANDATE:**
    - You MUST ALWAYS use this to **VERIFY** information from search results.
    - Snippets are insufficient; you MUST read full content for precise analysis.
    - When `summarize=True` (default), the content will be processed by a sub-agent to extract high-signal information while preserving references.

    **ARGS:**
    - `url`: The full web address.
    - `summarize`: Whether to summarize the content using a sub-agent (default: True).
    """
    try:
        html_content, links = await _fetch_page_content(url)
        markdown_content = _convert_html_to_markdown(html_content)

        if summarize:
            summarized_content = await _summarize_web_content(markdown_content, url)
            return {
                "content": summarized_content,
                "links_on_page": links,
                "summarized": True,
            }

        return {
            "content": markdown_content,
            "links_on_page": links,
            "summarized": False,
        }
    except Exception as e:
        return {"error": f"Failed to fetch content from {url}: {str(e)}"}


async def search_internet(
    query: str,
    page: int = 1,
) -> dict:
    """
    Performs a broad internet search.

    **RESEARCH MANDATE:**
    - Search snippets are for **DISCOVERY ONLY**.
    - You MUST ALWAYS use `OpenWebPage` on relevant URLs to extract full content.
    - Reports MUST include a 'Sources' or 'References' section listing all verified URLs.

    **ARGS:**
    - `query`: The search string.
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

        response = requests.get(url, headers={"User-Agent": user_agent}, timeout=30)
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


async def _summarize_web_content(markdown_content: str, url: str) -> str:
    """Summarize web content using an agent while preserving references."""
    # Create the summarization agent
    agent = create_agent(
        model=llm_config.model,
        system_prompt=get_web_summarizer_system_prompt(),
    )

    # Prepare the prompt data
    prompt_data = {
        "url": url,
        "content": markdown_content,
        "instruction": "Extract high-signal information from this web page content while preserving all essential references and citations. Focus on technical details, specifications, and actionable information.",
    }

    # Run the agent
    message = json.dumps(prompt_data)
    result, _ = await run_agent(
        agent=agent,
        message=message,
        message_history=[],  # Stateless
        limiter=llm_limiter,
    )

    return str(result)


search_internet.__name__ = "SearchInternet"

open_web_page.__name__ = "OpenWebPage"
