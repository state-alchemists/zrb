from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.http import generate_curl, http_request


def test_http_request_success():
    # Mock context
    ctx = MagicMock()
    ctx.input.method = "POST"
    ctx.input.url = "http://test.com"
    ctx.input.headers = '{"X-Test": "value"}'
    ctx.input.body = '{"foo": "bar"}'
    ctx.input.verify_ssl = True

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"

    with patch("requests.request", return_value=mock_response):
        # Call the underlying function directly to bypass BaseTask wrapper
        # The underlying function is available in the _action attribute
        res = http_request._action(ctx)
        assert res.status_code == 200
        assert res.text == "ok"
        assert ctx.print.called


def test_http_request_fail():
    ctx = MagicMock()
    ctx.input.method = "GET"
    ctx.input.url = "http://error.com"
    ctx.input.headers = "{}"
    ctx.input.body = "{}"
    ctx.input.verify_ssl = True

    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch("requests.request", return_value=mock_response):
        res = http_request._action(ctx)
        assert res.status_code == 500


def test_generate_curl_complex():
    ctx = MagicMock()
    ctx.input.method = "PUT"
    ctx.input.url = "http://api.com/v1"
    ctx.input.headers = '{"Auth": "token"}'
    ctx.input.body = '{"data": 1}'
    ctx.input.verify_ssl = False

    res = generate_curl._action(ctx)
    assert "-X PUT" in res
    assert "-H Auth: token" in res
    assert "--data-raw" in res
    assert "--insecure" in res


def test_generate_curl_simple():
    ctx = MagicMock()
    ctx.input.method = "GET"
    ctx.input.url = "http://google.com"
    ctx.input.headers = "{}"
    ctx.input.body = "{}"
    ctx.input.verify_ssl = True

    res = generate_curl._action(ctx)
    assert "curl -X GET" in res
    assert "google.com" in res
