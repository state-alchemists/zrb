import time
from typing import Any

import requests

from zrb.config.config import CFG
from zrb.llm.tool.search.http_errors import raise_http_error

_MAX_RATE_LIMIT_RETRIES = 1
_DEFAULT_RETRY_AFTER_SECONDS = 1.0


def search_internet(
    query: str,
    page: int = 1,
    safe_search: str = "",
    language: str = "",
    api_key: str = "",
) -> dict[str, Any]:
    """
    Searches the web via Brave Search. Use for current information, news, documentation,
    and resources not in the local codebase.
    """
    if not safe_search:
        safe_search = CFG.BRAVE_API_SAFE
    if not language:
        language = CFG.BRAVE_API_LANG

    effective_api_key = api_key or CFG.BRAVE_API_KEY

    if not effective_api_key:
        raise Exception(
            "Error: Brave API key not configured. "
            "[SYSTEM SUGGESTION]: Ask the user to provide their Brave API key. Pass it via the 'api_key' parameter in your next search_internet call."
        )

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    page = max(1, page)
    if page > 10:
        raise Exception(
            "Error: Brave Search supports at most 10 result pages. "
            "[SYSTEM SUGGESTION]: Retry with a page number from 1 through 10."
        )

    request_kwargs = {
        "headers": {
            "User-Agent": user_agent,
            "Accept": "application/json",
            "x-subscription-token": effective_api_key,
        },
        "params": {
            "q": query,
            "count": "10",
            "offset": page - 1,
            "safesearch": safe_search,
            "search_lang": language,
            "summary": "true",
        },
        "timeout": CFG.LLM_WEB_HTTP_TIMEOUT / 1000,
    }
    for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search", **request_kwargs
        )
        if response.status_code != 429 or attempt == _MAX_RATE_LIMIT_RETRIES:
            break
        time.sleep(_retry_after_seconds(response))
    if response.status_code != 200:
        raise_http_error(
            response,
            service_name="Brave Search",
            docs_url="https://brave.com/search/api/",
            key_label="Brave API key",
        )
    return response.json()


def _retry_after_seconds(response: requests.Response) -> float:
    """Return a safe delay for a Brave rate-limit retry."""
    retry_after = response.headers.get("Retry-After", "")
    try:
        return max(0.0, float(retry_after))
    except (TypeError, ValueError):
        return _DEFAULT_RETRY_AFTER_SECONDS
