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
    """
    if safe_search is None:
        safe_search = CFG.SEARXNG_SAFE
    if language is None:
        language = CFG.SEARXNG_LANG

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

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
