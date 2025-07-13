import asyncio
from unittest import mock

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.task.tcp_check import TcpCheck


@pytest.mark.asyncio
@mock.patch("asyncio.open_connection")
async def test_tcp_check_success(mock_open_connection):
    mock_reader, mock_writer = mock.MagicMock(), mock.MagicMock()
    mock_open_connection.return_value = (mock_reader, mock_writer)

    tcp_check = TcpCheck(name="test_tcp_check", interval=0)
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_tcp_check",
        color=1,
        icon="🔌",
    )
    result = await tcp_check._exec_action(ctx)

    assert result == (mock_reader, mock_writer)
    mock_open_connection.assert_called_once_with("localhost", 80)


@pytest.mark.asyncio
@mock.patch("asyncio.open_connection")
async def test_tcp_check_retry_and_succeed(mock_open_connection):
    mock_reader, mock_writer = mock.MagicMock(), mock.MagicMock()
    mock_open_connection.side_effect = [
        asyncio.TimeoutError,
        (mock_reader, mock_writer),
    ]

    tcp_check = TcpCheck(name="test_tcp_check", interval=0)
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_tcp_check",
        color=1,
        icon="🔌",
    )
    result = await tcp_check._exec_action(ctx)

    assert result == (mock_reader, mock_writer)
    assert mock_open_connection.call_count == 2


@pytest.mark.asyncio
@mock.patch("asyncio.open_connection", side_effect=Exception("Test error"))
async def test_tcp_check_exception(mock_open_connection):
    tcp_check = TcpCheck(name="test_tcp_check", interval=0)
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_tcp_check",
        color=1,
        icon="🔌",
    )

    async def run_check():
        await tcp_check._exec_action(ctx)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(run_check(), timeout=1)
