import shlex
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.http import generate_curl, http_request
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


@pytest.fixture
def session():
    return Session(shared_ctx=SharedContext(), state_logger=MagicMock())


@pytest.mark.asyncio
async def test_http_request(session):
    with patch("requests.request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = '{"foo": "bar"}'
        mock_request.return_value = mock_response

        res = await http_request.async_run(
            session=session,
            kwargs={
                "url": "http://example.com",
                "method": "GET",
                "headers": '{"Content-Type": "application/json"}',
                "body": "{}",
                "timeout": 10,
                "verify_ssl": True,
            },
        )
        assert res == mock_response


@pytest.mark.asyncio
async def test_generate_curl(session):
    res = await generate_curl.async_run(
        session=session,
        kwargs={
            "url": "http://example.com",
            "method": "POST",
            "headers": '{"Content-Type": "application/json"}',
            "body": '{"foo": "bar"}',
            "verify_ssl": True,
        },
    )
    assert "curl -X POST" in res
    assert "http://example.com" in res
