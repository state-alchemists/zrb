from typing import Any

import requests

from zrb.config.config import CFG


def search_internet(
    query: str,
    page: int = 1,
    safe_search: str | None = None,
    language: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """
    Performs a live internet search using SerpApi (Google Search) to retrieve the most relevant and current information from the web.

    **WHEN TO USE:**
    - When you need precise, high-quality search results from Google.
    - To find the latest official documentation, technical articles, or community discussions.

    **ARGS:**
    - `query`: The search string or question.
    - `page`: Result page number (default 1).
    - `api_key`: SerpApi key. Falls back to default if not provided.
    """
    if safe_search is None:
        safe_search = CFG.SERPAPI_SAFE
    if language is None:
        language = CFG.SERPAPI_LANG

    effective_api_key = api_key if api_key is not None else CFG.SERPAPI_KEY

    if not effective_api_key:
        raise Exception(
            "Error: SerpApi key not configured. "
            "[SYSTEM SUGGESTION]: Ask the user to provide their SerpApi key. Pass it via the 'api_key' parameter in your next search_internet call."
        )

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

    response = requests.get(
        "https://serpapi.com/search",
        headers={"User-Agent": user_agent},
        params={
            "q": query,
            "start": (page - 1) * 10,
            "hl": language,
            "safe": safe_search,
            "api_key": effective_api_key,
        },
    )
    if response.status_code != 200:
        error_body = (
            response.text[:500] if response.text else "No error details provided"
        )
        if response.status_code == 401:
            raise Exception(
                f"Error: SerpApi authentication failed (status code: {response.status_code}). "
                f"Response: {error_body}. "
                f"[SYSTEM SUGGESTION]: The API key is invalid or expired. Ask the user to verify their SerpApi key at https://serpapi.com/ and provide a valid one via the 'api_key' parameter."
            )
        elif response.status_code == 429:
            raise Exception(
                f"Error: SerpApi rate limit exceeded (status code: {response.status_code}). "
                f"Response: {error_body}. "
                f"[SYSTEM SUGGESTION]: You have exceeded your SerpApi plan limits. Wait before retrying, or ask the user to upgrade their SerpApi plan."
            )
        elif 400 <= response.status_code < 500:
            raise Exception(
                f"Error: SerpApi request failed (status code: {response.status_code}). "
                f"Response: {error_body}. "
                f"[SYSTEM SUGGESTION]: Check your search parameters. The 'language', 'safe_search', or 'query' may be invalid. Try simplifying the query or using default parameters."
            )
        else:
            raise Exception(
                f"Error: SerpApi server error (status code: {response.status_code}). "
                f"Response: {error_body}. "
                f"[SYSTEM SUGGESTION]: This is likely a temporary SerpApi server issue. Retry the search, or inform the user and try again later."
            )
    return response.json()
