from typing import Any

import requests

from zrb.config.config import CFG


def search_internet(
    query: str,
    page: int = 1,
    safe_search: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Performs an internet search using SerpApi (Google).

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
        safe_search (str | None): Safety setting. 'active' or 'off'.
            If None, uses the system default configuration.
        language (str | None): Two-letter language code (e.g., 'en', 'id').
            If None, uses the system default configuration.

    Returns:
        dict: Summary of search results (titles, links, snippets).
    """
    if safe_search is None:
        safe_search = CFG.SERPAPI_SAFE
    if language is None:
        language = CFG.SERPAPI_LANG

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa

    response = requests.get(
        "https://serpapi.com/search",
        headers={"User-Agent": user_agent},
        params={
            "q": query,
            "start": (page - 1) * 10,
            "hl": language,
            "safe": safe_search,
            "api_key": CFG.SERPAPI_KEY,
        },
    )
    if response.status_code != 200:
        raise Exception(
            f"Error: Unable to retrieve search results (status code: {response.status_code})"
        )
    return response.json()
