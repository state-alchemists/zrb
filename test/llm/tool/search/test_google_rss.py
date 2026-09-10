"""Tests for llm/tool/search/google_rss.py — covers the RSS-parse path."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from zrb.llm.tool.search.google_rss import search_internet

_RSS_PAYLOAD = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss>
  <channel>
    <item>
      <title>Article One</title>
      <link>https://example.com/1</link>
      <description>Snippet one</description>
      <source>Example News</source>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/2</link>
      <description>Snippet two</description>
      <pubDate>Tue, 02 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

_EMPTY_RSS = b"""<?xml version="1.0" encoding="UTF-8"?><rss></rss>"""


def _make_response(content: bytes):
    resp = MagicMock()
    resp.content = content
    resp.raise_for_status = MagicMock()
    return resp


def test_search_internet_parses_items():
    with patch("requests.get", return_value=_make_response(_RSS_PAYLOAD)) as mock_get:
        result = search_internet("python news")

    mock_get.assert_called_once()
    url = mock_get.call_args[0][0]
    assert "news.google.com/rss/search" in url
    assert "python+news" in url
    assert result["query"] == "python news"
    assert result["page"] == 1
    assert len(result["results"]) == 2

    first = result["results"][0]
    assert first["title"] == "Article One"
    assert first["url"] == "https://example.com/1"
    assert first["snippet"] == "Snippet one"
    assert first["source"] == "Example News"
    assert first["published"] == "Mon, 01 Jan 2024 00:00:00 GMT"

    # Missing <source> falls back to the default tag
    second = result["results"][1]
    assert second["source"] == "google_rss"


def test_search_internet_paginates_feed_items():
    items = "".join(
        f"<item><title>Article {index}</title>"
        f"<link>https://example.com/{index}</link></item>"
        for index in range(1, 13)
    )
    payload = f"<rss><channel>{items}</channel></rss>".encode()

    with patch("requests.get", return_value=_make_response(payload)):
        result = search_internet("python news", page=2)

    assert [item["title"] for item in result["results"]] == [
        "Article 11",
        "Article 12",
    ]
    assert result["page"] == 2


def test_search_internet_handles_empty_channel():
    with patch("requests.get", return_value=_make_response(_EMPTY_RSS)):
        result = search_internet("nothing")
    assert result["results"] == []
    assert result["query"] == "nothing"
    assert result["page"] == 1


def test_search_internet_propagates_http_errors():
    resp = MagicMock()
    resp.raise_for_status.side_effect = RuntimeError("502")
    with patch("requests.get", return_value=resp):
        try:
            search_internet("x")
        except RuntimeError as e:
            assert "502" in str(e)
        else:
            raise AssertionError("Expected RuntimeError to propagate")


def test_search_internet_connection_error_has_suggestion():
    with patch(
        "requests.get", side_effect=requests.exceptions.ConnectionError("refused")
    ):
        with pytest.raises(Exception) as excinfo:
            search_internet("x")
    assert "Unable to connect" in str(excinfo.value)
    assert "[SYSTEM SUGGESTION]" in str(excinfo.value)


def test_search_internet_timeout_has_suggestion():
    with patch("requests.get", side_effect=requests.exceptions.Timeout("timed out")):
        with pytest.raises(Exception) as excinfo:
            search_internet("x")
    assert "timed out" in str(excinfo.value)
    assert "[SYSTEM SUGGESTION]" in str(excinfo.value)
