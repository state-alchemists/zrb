import json

from zrb.config.config import CFG
from zrb.llm.agent import create_agent, run_agent
from zrb.llm.config.config import llm_config
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.prompt.prompt import get_web_summarizer_system_prompt


async def open_web_page(url: str, summarize: bool = True) -> dict:
    """
    Fetches a web page and returns it as Markdown. Includes links found on the page.

    When `summarize=True` (default), a sub-agent extracts high-signal info and reduces token usage.
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
                "url": url,
            }

        return {
            "content": markdown_content,
            "links_on_page": links,
            "summarized": False,
            "url": url,
        }
    except Exception as e:
        return {"error": f"Failed to fetch content from {url}: {str(e)}", "url": url}


async def search_internet(
    query: str,
    page: int = 1,
) -> dict:
    """
    Performs an internet search. Returns a normalized dict with:
        - query: the search query
        - results: list of {title, url, snippet, source}
        - total: number of results
        - page: current page
        - error: null on success, error string on failure

    Requires SERPAPI_KEY, BRAVE_API_KEY, or SearXNG configuration.
    """
    method = CFG.SEARCH_INTERNET_METHOD.strip().lower()
    if method == "serpapi" and CFG.SERPAPI_KEY:
        from zrb.llm.tool.search.serpapi import search_internet as serpapi_search

        try:
            raw = serpapi_search(query, page=page)
        except Exception as e:  # noqa: BLE001
            return _error_result(query, page, str(e), "serpapi")
        return normalize_search_result(raw, "serpapi")

    if method == "brave" and CFG.BRAVE_API_KEY:
        from zrb.llm.tool.search.brave import search_internet as brave_search

        try:
            raw = brave_search(query, page=page)
        except Exception as e:  # noqa: BLE001
            return _error_result(query, page, str(e), "brave")
        return normalize_search_result(raw, "brave")

    from zrb.llm.tool.search.searxng import search_internet as searxng_search

    try:
        raw = searxng_search(query, page=page)
    except Exception as e:  # noqa: BLE001
        return _error_result(query, page, str(e), "searxng")
    return normalize_search_result(raw, "searxng")


def normalize_search_result(raw: dict, backend: str) -> dict:
    """Normalize search results from any backend into a consistent schema."""
    if "error" in raw:
        return raw
    query = raw.get("query", "")
    if backend == "brave":
        return _normalize_brave(raw, query)
    if backend == "serpapi":
        return _normalize_serpapi(raw, query)
    if backend == "searxng":
        return _normalize_searxng(raw, query)
    return raw


def _normalize_brave(raw: dict, query: str) -> dict:
    web_results = raw.get("web", {}).get("results", [])
    results = []
    for item in web_results[:10]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", "")
                or item.get("extra_snippets", [""])[0],
                "source": "brave",
            }
        )
    return {
        "query": query,
        "results": results,
        "total": len(results),
        "page": 1,
        "error": None,
    }


def _normalize_serpapi(raw: dict, query: str) -> dict:
    organic = raw.get("organic_results", [])
    results = []
    for item in organic[:10]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "serpapi",
            }
        )
    return {
        "query": query,
        "results": results,
        "total": len(results),
        "page": 1,
        "error": None,
    }


def _normalize_searxng(raw: dict, query: str) -> dict:
    results = []
    for item in raw.get("results", [])[:10]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "source": "searxng",
            }
        )
    return {
        "query": query,
        "results": results,
        "total": len(results),
        "page": raw.get("pageno", 1),
        "error": None,
    }


def _error_result(query: str, page: int, message: str, backend: str) -> dict:
    return {
        "query": query,
        "results": [],
        "total": 0,
        "page": page,
        "error": message,
    }


async def _fetch_page_content(url: str) -> tuple:
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": user_agent})
            await page.goto(
                url, wait_until="networkidle", timeout=CFG.LLM_WEB_PAGE_TIMEOUT
            )
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

        response = requests.get(
            url,
            headers={"User-Agent": user_agent},
            timeout=CFG.LLM_WEB_HTTP_TIMEOUT / 1000,
        )
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
