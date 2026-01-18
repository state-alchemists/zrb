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
    Performs a live internet search using SerpApi (Google Search) to retrieve the most relevant and current information from the web.

    **WHEN TO USE:**
    - When you need precise, high-quality search results from Google.
    - To find the latest official documentation, technical articles, or community discussions.

    **ARGS:**
    - `query`: The search string or question.
    - `page`: Result page number (default 1).
    """
    if safe_search is None:
        safe_search = CFG.SERPAPI_SAFE
    if language is None:
        language = CFG.SERPAPI_LANG

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

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
