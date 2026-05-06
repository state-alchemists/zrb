"""Google News RSS search backend — free, no API key, no Docker required."""

import xml.etree.ElementTree as ET
from urllib.parse import quote_plus


def search_internet(query: str, page: int = 1) -> dict:
    """Fetch search results from Google News RSS."""
    import requests

    url = (
        f"https://news.google.com/rss/search"
        f"?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else []

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
