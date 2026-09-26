from typing import Any

import requests

from zrb.config.config import CFG
from zrb.llm.tool.search.http_errors import (
    BROWSER_USER_AGENT,
    SearchToolError,
    raise_http_error,
)


def search_internet(
    query: str,
    page: int = 1,
    safe_search: str = "",
    language: str = "",
    api_key: str = "",
) -> dict[str, Any]:
    """
    Searches the web via SerpApi (Google). Use for high-quality current results —
    documentation, technical articles, and community discussions.
    """
    if not safe_search:
        safe_search = CFG.SERPAPI_SAFE
    if not language:
        language = CFG.SERPAPI_LANG

    effective_api_key = api_key or CFG.SERPAPI_KEY

    if not effective_api_key:
        raise SearchToolError(
            "Error: SerpApi key not configured. "
            "[SYSTEM SUGGESTION]: Ask the user to provide their SerpApi key. Pass it via the 'api_key' parameter in your next search_internet call."
        )

    user_agent = BROWSER_USER_AGENT

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
        timeout=CFG.LLM_WEB_HTTP_TIMEOUT / 1000,
    )
    if response.status_code != 200:
        raise_http_error(
            response,
            service_name="SerpApi",
            docs_url="https://serpapi.com/",
            key_label="SerpApi key",
        )
    return response.json()
