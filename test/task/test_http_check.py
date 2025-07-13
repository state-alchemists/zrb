import asyncio
from unittest import mock

import pytest
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.task.http_check import HttpCheck


@pytest.mark.asyncio
@mock.patch("requests.request")
async def test_http_check_success(mock_request):
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_request.return_value = mock_response

    http_check = HttpCheck(name="test_http_check", interval=0)
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_http_check",
        color=1,
        icon="🌐",
    )
    result = await http_check._exec_action(ctx)

    assert result == mock_response
    mock_request.assert_called_once_with("GET", "http://localhost")


@pytest.mark.asyncio
@mock.patch("requests.request")
async def test_http_check_retry_and_succeed(mock_request):
    mock_response_fail = mock.MagicMock()
    mock_response_fail.status_code = 500
    mock_response_success = mock.MagicMock()
    mock_response_success.status_code = 200
    mock_request.side_effect = [mock_response_fail, mock_response_success]

    http_check = HttpCheck(name="test_http_check", interval=0)
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_http_check",
        color=1,
        icon="🌐",
    )
    result = await http_check._exec_action(ctx)

    assert result == mock_response_success
    assert mock_request.call_count == 2


@pytest.mark.asyncio
@mock.patch("requests.request", side_effect=Exception("Test error"))
async def test_http_check_exception(mock_request):
    http_check = HttpCheck(name="test_http_check", interval=0)
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_http_check",
        color=1,
        icon="🌐",
    )

    async def run_check():
        await http_check._exec_action(ctx)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(run_check(), timeout=1)
