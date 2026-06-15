from unittest import mock

import pytest

from zrb.builtin.http import generate_curl, http_request
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


def _mock_response():
    response = mock.MagicMock()
    response.status_code = 200
    response.text = "ok"
    response.url = "http://test.com"
    response.headers = {}
    return response


@pytest.mark.asyncio
async def test_http_request_returns_body():
    response = _mock_response()
    with mock.patch("requests.request", return_value=response) as mock_request:
        res = await http_request.async_run(
            session=get_session(),
            kwargs={
                "method": "POST",
                "url": "http://test.com",
                "params": '{"q": "1"}',
                "headers": '{"X-Test": "value"}',
                "body_format": "json",
                "body": '{"foo": "bar"}',
                "timeout": 10,
                "verify_ssl": True,
            },
        )
    # The body (not the Response object) is returned so stdout is pipe-friendly.
    assert res == "ok"
    _, called_kwargs = mock_request.call_args
    assert called_kwargs["json"] == {"foo": "bar"}
    assert called_kwargs["params"] == {"q": "1"}
    assert called_kwargs["timeout"] == 10


@pytest.mark.asyncio
async def test_http_request_form_body():
    response = _mock_response()
    with mock.patch("requests.request", return_value=response) as mock_request:
        await http_request.async_run(
            session=get_session(),
            kwargs={
                "method": "POST",
                "url": "http://test.com",
                "params": "{}",
                "headers": "{}",
                "body_format": "form",
                "body": '{"foo": "bar"}',
                "timeout": 30,
                "verify_ssl": True,
            },
        )
    _, called_kwargs = mock_request.call_args
    assert called_kwargs["data"] == {"foo": "bar"}
    assert "json" not in called_kwargs


@pytest.mark.asyncio
async def test_http_request_raw_body():
    response = _mock_response()
    with mock.patch("requests.request", return_value=response) as mock_request:
        await http_request.async_run(
            session=get_session(),
            kwargs={
                "method": "POST",
                "url": "http://test.com",
                "params": "{}",
                "headers": "{}",
                "body_format": "raw",
                "body": "plain text",
                "timeout": 30,
                "verify_ssl": True,
            },
        )
    _, called_kwargs = mock_request.call_args
    assert called_kwargs["data"] == "plain text"


@pytest.mark.asyncio
async def test_http_request_error_status_returns_body():
    response = _mock_response()
    response.status_code = 404
    response.reason = "Not Found"
    response.text = '{"error": "nope"}'
    with mock.patch("requests.request", return_value=response):
        res = await http_request.async_run(
            session=get_session(),
            kwargs={
                "method": "GET",
                "url": "http://test.com",
                "params": "{}",
                "headers": "{}",
                "body_format": "json",
                "body": "",
                "timeout": 30,
                "verify_ssl": True,
            },
        )
    # Body is still returned (it often carries error detail); status is on stderr.
    assert res == '{"error": "nope"}'


@pytest.mark.asyncio
async def test_http_request_failure_raises():
    with mock.patch("requests.request", side_effect=RuntimeError("boom")):
        with pytest.raises(Exception):
            await http_request.async_run(
                session=get_session(),
                kwargs={
                    "method": "GET",
                    "url": "http://error.com",
                    "params": "{}",
                    "headers": "{}",
                    "body_format": "json",
                    "body": "",
                    "timeout": 30,
                    "verify_ssl": True,
                },
            )


@pytest.mark.asyncio
async def test_generate_curl_complex():
    res = await generate_curl.async_run(
        session=get_session(),
        kwargs={
            "method": "PUT",
            "url": "http://api.com/v1",
            "headers": '{"Auth": "token"}',
            "body": '{"data": 1}',
            "verify_ssl": False,
        },
    )
    assert "-X PUT" in res
    assert "Auth: token" in res
    assert "--data-raw" in res
    assert "--insecure" in res


@pytest.mark.asyncio
async def test_generate_curl_simple():
    res = await generate_curl.async_run(
        session=get_session(),
        kwargs={
            "method": "GET",
            "url": "http://google.com",
            "headers": "{}",
            "body": "",
            "verify_ssl": True,
        },
    )
    assert "curl -X GET" in res
    assert "google.com" in res
