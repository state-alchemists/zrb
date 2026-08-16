"""Tests for the shared HTTP-status error helper used by brave.py/serpapi.py."""

from unittest.mock import MagicMock

import pytest

from zrb.llm.tool.search._http_errors import raise_http_error


def _response(status_code: int, text: str = "some error body"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


@pytest.mark.parametrize(
    "status_code,expected_substring",
    [
        (401, "authentication failed"),
        (429, "rate limit exceeded"),
        (400, "request failed"),
        (500, "server error"),
    ],
)
def test_raise_http_error_message_by_status(status_code, expected_substring):
    with pytest.raises(Exception) as excinfo:
        raise_http_error(
            _response(status_code),
            service_name="Example Search",
            docs_url="https://example.com/docs",
            key_label="Example API key",
        )
    message = str(excinfo.value)
    assert expected_substring in message
    assert "[SYSTEM SUGGESTION]" in message
    assert str(status_code) in message


def test_raise_http_error_401_includes_docs_url_and_key_label():
    with pytest.raises(Exception) as excinfo:
        raise_http_error(
            _response(401),
            service_name="Example Search",
            docs_url="https://example.com/docs",
            key_label="Example API key",
        )
    message = str(excinfo.value)
    assert "https://example.com/docs" in message
    assert "Example API key" in message


def test_raise_http_error_no_error_details_fallback():
    with pytest.raises(Exception) as excinfo:
        raise_http_error(
            _response(500, text=""),
            service_name="Example Search",
            docs_url="https://example.com/docs",
            key_label="Example API key",
        )
    assert "No error details provided" in str(excinfo.value)
