import asyncio
from unittest import mock

import pytest

from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.tcp_check import TcpCheck


@pytest.fixture
def mock_session():
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_tcp_check_success(mock_session):
    mock_reader, mock_writer = mock.MagicMock(), mock.MagicMock()

    async def mock_open_connection(host, port):
        return (mock_reader, mock_writer)

    tcp_check = TcpCheck(name="test_tcp_check")
    mock_session.register_task(tcp_check)

    # Directly replace the function to avoid AsyncMock
    original_open_connection = asyncio.open_connection
    asyncio.open_connection = mock_open_connection
    try:
        result = await tcp_check.exec(mock_session)
    finally:
        asyncio.open_connection = original_open_connection

    assert result is True


@pytest.mark.asyncio
async def test_tcp_check_retry_and_succeed(mock_session):
    mock_reader, mock_writer = mock.MagicMock(), mock.MagicMock()

    # Create side effect that handles both exception and success
    call_count = 0

    async def mock_open_connection(host, port):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise asyncio.TimeoutError("Test timeout")
        else:
            return (mock_reader, mock_writer)

    # MagicMock sleep to return immediately
    async def mock_sleep(delay):
        return None

    tcp_check = TcpCheck(name="test_tcp_check")
    mock_session.register_task(tcp_check)

    original_open_connection = asyncio.open_connection
    original_sleep = asyncio.sleep
    asyncio.open_connection = mock_open_connection
    asyncio.sleep = mock_sleep
    try:
        result = await tcp_check.exec(mock_session)
    finally:
        asyncio.open_connection = original_open_connection
        asyncio.sleep = original_sleep

    assert result is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_tcp_check_exception(mock_session):
    # Create a mock for open_connection that always raises an exception
    async def mock_open_connection(host, port):
        raise Exception("Test error")

    # Create a mock for sleep that returns a never-completing coroutine
    # This allows wait_for to timeout without warnings
    async def mock_sleep_coro(delay):
        # Create a future that never completes
        # This allows wait_for to timeout naturally
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        try:
            await fut
        except asyncio.CancelledError:
            # Properly handle cancellation when wait_for times out
            fut.cancel()
            raise
        return None

    tcp_check = TcpCheck(name="test_tcp_check")
    mock_session.register_task(tcp_check)

    original_open_connection = asyncio.open_connection
    original_sleep = asyncio.sleep
    asyncio.open_connection = mock_open_connection
    asyncio.sleep = mock_sleep_coro
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(tcp_check.exec(mock_session), timeout=1)
    finally:
        asyncio.open_connection = original_open_connection
        asyncio.sleep = original_sleep


@pytest.mark.asyncio
@pytest.mark.parametrize("interval", [0, -1])
async def test_tcp_check_rejects_a_non_positive_interval(mock_session, interval):
    """A non-positive interval would make asyncio.sleep spin, hammering the host."""
    async def mock_open_connection(host, port):
        raise AssertionError("a rejected interval must not probe")

    tcp_check = TcpCheck(name="test_tcp_check", interval=interval)
    mock_session.register_task(tcp_check)

    with (
        mock.patch("asyncio.open_connection", mock_open_connection),
        pytest.raises(ValueError) as exc_info,
    ):
        await tcp_check.exec(mock_session)

    message = str(exc_info.value)
    assert "TcpCheck" in message
    assert "`interval`" in message
    assert str(interval) in message


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_interval", ["0", "-500"])
async def test_tcp_check_rejects_a_non_positive_configured_interval(
    mock_session, monkeypatch, raw_interval
):
    """The CFG-backed interval is rejected too, naming the setting."""
    monkeypatch.setenv("ZRB_TCP_CHECK_INTERVAL", raw_interval)

    tcp_check = TcpCheck(name="test_tcp_check")
    mock_session.register_task(tcp_check)

    with pytest.raises(ValueError) as exc_info:
        await tcp_check.exec(mock_session)

    message = str(exc_info.value)
    assert "ZRB_TCP_CHECK_INTERVAL" in message
    assert raw_interval in message


@pytest.mark.asyncio
async def test_tcp_check_bounds_a_hanging_connect_and_retries(mock_session):
    """A blackholed host must hit the probe timeout, not wait on the OS."""
    call_count = 0
    mock_reader, mock_writer = mock.MagicMock(), mock.MagicMock()

    async def mock_open_connection(host, port):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Never connects. `wait_for` cancels this on the probe timeout.
            await asyncio.Event().wait()
        return (mock_reader, mock_writer)

    async def mock_sleep(delay):
        return None

    tcp_check = TcpCheck(name="test_tcp_check")
    mock_session.register_task(tcp_check)

    with (
        mock.patch("asyncio.open_connection", mock_open_connection),
        mock.patch("asyncio.sleep", mock_sleep),
        mock.patch("zrb.task.tcp_check._MIN_PROBE_TIMEOUT", 0.01),
    ):
        result = await tcp_check.exec(mock_session)

    assert result is True
    assert call_count == 2
