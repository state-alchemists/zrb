import asyncio
from unittest.mock import MagicMock, patch, Mock

import pytest

from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.http_check import HttpCheck


@pytest.fixture
def mock_session():
    shared_ctx = SharedContext(logging_level=20)
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_http_check_success(mock_session):
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("requests.request", return_value=mock_response) as mock_request:
        http_check = HttpCheck(name="test_http_check")
        mock_session.register_task(http_check)

        result = await http_check.exec(mock_session)

        assert result == mock_response
        mock_request.assert_called_once_with("GET", "http://localhost")


@pytest.mark.asyncio
async def test_http_check_retry_and_succeed(mock_session):
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200

    # Create a simple async function for sleep
    sleep_called = []
    
    async def mock_sleep(delay):
        sleep_called.append(delay)
        return None
    
    with patch(
        "requests.request", side_effect=[mock_response_fail, mock_response_success]
    ) as mock_request, patch("asyncio.sleep", side_effect=mock_sleep):
        http_check = HttpCheck(name="test_http_check")
        mock_session.register_task(http_check)

        result = await http_check.exec(mock_session)

        assert result == mock_response_success
        assert mock_request.call_count == 2
        assert len(sleep_called) == 1


@pytest.mark.asyncio
async def test_http_check_exception(mock_session):
    with patch(
        "requests.request", side_effect=Exception("Test error")
    ) as mock_request:
        # Create a mock for sleep that returns a never-completing coroutine
        # This allows wait_for to timeout without warnings
        mock_sleep = Mock()
        
        async def mock_sleep_coro(delay):
            # Create a future that never completes
            # This allows wait_for to timeout naturally
            loop = asyncio.get_event_loop()
            fut = loop.create_future()
            try:
                await fut
            except asyncio.CancelledError:
                # Properly handle cancellation when wait_for times out
                fut.cancel()
                raise
            return None
        
        mock_sleep.side_effect = mock_sleep_coro
        
        with patch("asyncio.sleep", mock_sleep):
            http_check = HttpCheck(name="test_http_check")
            mock_session.register_task(http_check)

            with pytest.raises(asyncio.TimeoutError):
                # Use a reasonable timeout
                await asyncio.wait_for(http_check.exec(mock_session), timeout=0.1)

            assert mock_request.call_count > 0
