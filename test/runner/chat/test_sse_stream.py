"""Tests for sse_stream.py."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest


class TestSSEStreamResponse:
    def test_initialization(self):
        from zrb.runner.chat.sse_stream import SSEStreamResponse

        mock_session = MagicMock()
        mock_session.output_queue = asyncio.Queue()
        mock_manager = MagicMock()
        mock_manager.get_session.return_value = mock_session

        response = SSEStreamResponse(
            session_id="test-session",
            session_manager=mock_manager,
        )
        assert response.session_id == "test-session"
        assert response._queue is not None

    def test_headers(self):
        from zrb.runner.chat.sse_stream import SSEStreamResponse

        mock_session = MagicMock()
        mock_session.output_queue = asyncio.Queue()
        mock_manager = MagicMock()
        mock_manager.get_session.return_value = mock_session

        response = SSEStreamResponse(
            session_id="test-session",
            session_manager=mock_manager,
        )
        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["Connection"] == "keep-alive"
        assert response.headers["X-Accel-Buffering"] == "no"
        assert response.media_type == "text/event-stream"

    def test_session_id_assignment(self):
        from zrb.runner.chat.sse_stream import SSEStreamResponse

        mock_session = MagicMock()
        mock_session.output_queue = asyncio.Queue()
        mock_manager = MagicMock()
        mock_manager.get_session.return_value = mock_session

        response = SSEStreamResponse(
            session_id="my-session-id",
            session_manager=mock_manager,
        )
        assert response.session_id == "my-session-id"

    def test_queue_from_session(self):
        from zrb.runner.chat.sse_stream import SSEStreamResponse

        mock_queue = asyncio.Queue()
        mock_session = MagicMock()
        mock_session.output_queue = mock_queue
        mock_manager = MagicMock()
        mock_manager.get_session.return_value = mock_session

        response = SSEStreamResponse(
            session_id="test",
            session_manager=mock_manager,
        )
        assert response._queue is mock_queue

    @pytest.mark.asyncio
    async def test_event_generator_connected_event(self):
        """Test that the generator yields a connected event first."""
        from zrb.runner.chat.sse_stream import SSEStreamResponse

        mock_queue = asyncio.Queue()
        mock_session = MagicMock()
        mock_session.output_queue = mock_queue
        mock_manager = MagicMock()
        mock_manager.get_session.return_value = mock_session

        response = SSEStreamResponse(
            session_id="test-session",
            session_manager=mock_manager,
        )

        # Get the generator from the response body
        generator = response.body_iterator
        first_event = await generator.__anext__()

        # Should start with connected event
        assert first_event.startswith("event: connected\n")
        data = json.loads(first_event.split("data: ")[1])
        assert data["status"] == "connected"
        assert data["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_event_generator_dict_item(self):
        """Test processing a dict item from the queue."""
        from zrb.runner.chat.sse_stream import SSEStreamResponse

        mock_queue = asyncio.Queue()
        # Put a dict item in the queue
        await mock_queue.put({"text": "hello", "kind": "user"})
        mock_session = MagicMock()
        mock_session.output_queue = mock_queue
        mock_manager = MagicMock()
        mock_manager.get_session.return_value = mock_session

        response = SSEStreamResponse(
            session_id="test-session",
            session_manager=mock_manager,
        )

        generator = response.body_iterator
        _ = await generator.__anext__()  # connected event
        data_event = await generator.__anext__()

        # Should contain the text and type
        assert data_event.startswith("data: ")
        data = json.loads(data_event.split("data: ")[1])
        assert data["text"] == "hello"
        assert data["type"] == "user"

    @pytest.mark.asyncio
    async def test_event_generator_string_item(self):
        """Test processing a string item from the queue."""
        from zrb.runner.chat.sse_stream import SSEStreamResponse

        mock_queue = asyncio.Queue()
        # Put a string item in the queue
        await mock_queue.put("plain text message")
        mock_session = MagicMock()
        mock_session.output_queue = mock_queue
        mock_manager = MagicMock()
        mock_manager.get_session.return_value = mock_session

        response = SSEStreamResponse(
            session_id="test-session",
            session_manager=mock_manager,
        )

        generator = response.body_iterator
        _ = await generator.__anext__()  # connected event
        data_event = await generator.__anext__()

        assert data_event.startswith("data: ")
        data = json.loads(data_event.split("data: ")[1])
        assert data["text"] == "plain text message"
        assert data["type"] == "text"

    @pytest.mark.asyncio
    async def test_event_generator_timeout_keepalive(self):
        """Test that a timeout yields a keepalive message."""
        from zrb.runner.chat.sse_stream import SSEStreamResponse

        mock_queue = asyncio.Queue()
        mock_session = MagicMock()
        mock_session.output_queue = mock_queue
        mock_manager = MagicMock()
        mock_manager.get_session.return_value = mock_session

        response = SSEStreamResponse(
            session_id="test-session",
            session_manager=mock_manager,
        )

        generator = response.body_iterator
        _ = await generator.__anext__()  # connected event

        # Patch the timeout to be very short for testing
        with patch("asyncio.wait_for") as mock_wait_for:
            mock_wait_for.side_effect = asyncio.TimeoutError
            keepalive_event = await generator.__anext__()
            assert keepalive_event == ": keepalive\n\n"

    @pytest.mark.asyncio
    async def test_event_generator_cancelled_error(self):
        """Test that CancelledError breaks the generator loop."""
        from zrb.runner.chat.sse_stream import SSEStreamResponse

        mock_queue = asyncio.Queue()
        mock_session = MagicMock()
        mock_session.output_queue = mock_queue
        mock_manager = MagicMock()
        mock_manager.get_session.return_value = mock_session

        response = SSEStreamResponse(
            session_id="test-session",
            session_manager=mock_manager,
        )

        generator = response.body_iterator
        _ = await generator.__anext__()  # connected event

        with patch("asyncio.wait_for") as mock_wait_for:
            mock_wait_for.side_effect = asyncio.CancelledError
            # CancelledError should cause StopAsyncIteration
            with pytest.raises(StopAsyncIteration):
                await generator.__anext__()
