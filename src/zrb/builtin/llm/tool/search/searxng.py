from typing import Any

import requests

from zrb.config.config import CFG


def search_internet(
    query: str,
    page: int = 1,
    safe_search: int | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Performs an internet search using SearXNG.

    Use this tool to find up-to-date information, answer questions about current events,
    or research topics using a search engine.

    **EFFICIENCY TIP:**
    Make your `query` specific and keyword-rich to get the best results in a single call.
    Avoid vague queries that require follow-up searches.
    Bad: "new python features"
    Good: "python 3.12 new features list release date"

    Args:
        query (str): The natural language search query (e.g., 'Soto Madura').
            Do NOT include instructions, meta-talk, or internal reasoning.
            Use concise terms as a human would in a search engine.
        page (int): Search result page number. Defaults to 1.
        safe_search (int | None): Safety setting. 0 (None), 1 (Moderate), 2 (Strict).
            If None, uses the system default configuration.
        language (str | None): Language code (e.g., 'en').
            If None, uses the system default configuration.

    Returns:
        dict: Summary of search results (titles, links, snippets).
    """
    if safe_search is None:
        safe_search = CFG.SEARXNG_SAFE
    if language is None:
        language = CFG.SEARXNG_LANG

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa

    response = requests.get(
        url=f"{CFG.SEARXNG_BASE_URL}/search",
        headers={"User-Agent": user_agent},
        params={
            "q": query,
            "format": "json",
            "pageno": page,
            "safesearch": safe_search,
            "language": language,
        },
    )
    if response.status_code != 200:
        raise Exception(
            f"Error: Unable to retrieve search results (status code: {response.status_code})"
        )
    return response.json()
