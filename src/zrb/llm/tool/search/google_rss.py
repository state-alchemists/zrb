"""Google News RSS search backend — free, no API key, no Docker required."""

import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

_RESULTS_PER_PAGE = 10


def search_internet(query: str, page: int = 1) -> dict:
    """Fetch search results from Google News RSS."""
    # lazy: heavy third-party
    import requests

    # lazy: transitively heavy via internal — http_errors.py imports requests
    from zrb.llm.tool.search.http_errors import SearchToolError

    url = (
        f"https://news.google.com/rss/search"
        f"?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
    except requests.exceptions.ConnectionError as e:
        raise SearchToolError(
            "Error: Unable to connect to Google News RSS. Connection refused. "
            "[SYSTEM SUGGESTION]: This is likely a transient network issue or a "
            "firewall blocking news.google.com. Retry the search, or try a "
            "different search backend."
        ) from e
    except requests.exceptions.Timeout as e:
        raise SearchToolError(
            "Error: Connection to Google News RSS timed out. "
            "[SYSTEM SUGGESTION]: This is likely a transient network issue. Retry "
            "the search, or try a different search backend."
        ) from e
    response.raise_for_status()

    root = ET.fromstring(response.content)
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else []
    page = max(1, page)
    start = (page - 1) * _RESULTS_PER_PAGE
    items = items[start : start + _RESULTS_PER_PAGE]

    results = []
    for item in items:
        source_el = item.find("source")
        results.append(
            {
                "title": item.findtext("title", ""),
                "url": item.findtext("link", ""),
                "snippet": item.findtext("description", ""),
                "source": source_el.text if source_el is not None else "google_rss",
                "published": item.findtext("pubDate", ""),
            }
        )

    return {"query": query, "results": results, "page": page}
