"""Tests for sse_stream.py."""

import asyncio
from unittest.mock import MagicMock

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
