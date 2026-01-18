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
    Performs an internet search using Brave Search.
    """
    if safe_search is None:
        safe_search = CFG.BRAVE_API_SAFE
    if language is None:
        language = CFG.BRAVE_API_LANG

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
            "x-subscription-token": CFG.BRAVE_API_KEY,
        },
        params={
            "q": query,
            "count": "10",
            "offset": (page - 1) * 10,
            "safesearch": safe_search,
            "search_lang": language,
            "summary": "true",
        },
    )
    if response.status_code != 200:
        raise Exception(
            f"Error: Unable to retrieve search results (status code: {response.status_code})"
        )
    return response.json()
