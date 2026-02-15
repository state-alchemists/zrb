from unittest.mock import MagicMock, patch

import pytest
import requests

from zrb.llm.tool.search.brave import search_internet as brave_search
from zrb.llm.tool.search.searxng import search_internet as searxng_search
from zrb.llm.tool.search.serpapi import search_internet as serpapi_search


@patch("requests.get")
def test_brave_search_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_get.return_value = mock_response

    result = brave_search("query")
    assert result == {"results": []}


@patch("requests.get")
def test_serpapi_search_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"organic_results": []}
    mock_get.return_value = mock_response

    result = serpapi_search("query")
    assert result == {"organic_results": []}


@patch("requests.get")
def test_searxng_search_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_get.return_value = mock_response

    result = searxng_search("query")
    assert result == {"results": []}


@patch("requests.get")
def test_searxng_search_connection_error(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("Refused")

    with pytest.raises(Exception) as excinfo:
        searxng_search("query")
    assert "Unable to connect to Searxng" in str(excinfo.value)
