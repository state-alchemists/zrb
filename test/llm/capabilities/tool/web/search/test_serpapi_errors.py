"""SerpApi errors must not echo the request URL: it carries `api_key`."""

import os
from unittest.mock import patch

import pytest
import requests

from zrb.config.config import CFG
from zrb.llm.capabilities.tool.web import search_internet
from zrb.llm.capabilities.tool.web.search.http_errors import SearchToolError
from zrb.llm.capabilities.tool.web.search.serpapi import (
    search_internet as serpapi_search,
)


def test_serpapi_request_error_does_not_leak_the_api_key():
    """`requests` embeds the prepared query string — `api_key` included — in its
    connection and timeout errors, and `search_internet` hands that text to the
    model as the tool error. The backend must name only the exception type."""
    with patch("zrb.llm.capabilities.tool.web.search.serpapi.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='serpapi.com', port=443): Max retries "
            "exceeded with url: /search?q=cats&api_key=SECRET (Caused by "
            "NewConnectionError(...))"
        )
        with pytest.raises(SearchToolError) as error_info:
            serpapi_search("cats", api_key="SECRET")

    message = str(error_info.value)
    assert "SECRET" not in message
    assert "api_key" not in message
    assert "ConnectionError" in message


@pytest.mark.asyncio
async def test_search_internet_serpapi_network_error_does_not_leak_the_api_key():
    with (
        patch.dict(
            os.environ,
            {
                f"{CFG.ENV_PREFIX}_SEARCH_INTERNET_METHOD": "serpapi",
                "SERPAPI_KEY": "SECRET",
            },
        ),
        patch("zrb.llm.capabilities.tool.web.search.serpapi.requests.get") as mock_get,
    ):
        mock_get.side_effect = requests.exceptions.ConnectionError(
            "Max retries exceeded with url: /search?api_key=SECRET"
        )
        result = await search_internet("cats")

    assert "SECRET" not in str(result["error"])
    assert "ConnectionError" in str(result["error"])
