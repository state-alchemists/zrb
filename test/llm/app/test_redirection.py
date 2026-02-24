import os
import sys
import threading
import time
from unittest.mock import MagicMock

import pytest

from zrb.llm.app.redirection import GlobalStreamCapture


def test_global_stream_capture_initialization():
    """Test GlobalStreamCapture initialization."""
    mock_callback = MagicMock()
    capture = GlobalStreamCapture(mock_callback)

    assert capture.ui_callback == mock_callback
    assert capture.capturing is False
    assert capture.thread is None
    assert capture.pipe_r is None
    assert capture.pipe_w is None
    assert capture._buffer == []
    assert hasattr(capture, "original_stdout_fd")
    assert hasattr(capture, "original_stderr_fd")


def test_global_stream_capture_start_stop():
    """Test starting and stopping capture."""
    mock_callback = MagicMock()
    capture = GlobalStreamCapture(mock_callback)

    # Start capture
    capture.start()
    assert capture.capturing is True
    assert capture.thread is not None
    assert capture.thread.is_alive()
    assert capture.pipe_r is not None
    assert capture.pipe_w is not None

    # Stop capture
    capture.stop()
    assert capture.capturing is False
    assert capture.thread is None
    # pipe_r is closed by _reader context manager but variable may still hold fd
    # pipe_w should be None
    assert capture.pipe_w is None


def test_global_stream_capture_double_start():
    """Test that calling start twice doesn't create issues."""
    mock_callback = MagicMock()
    capture = GlobalStreamCapture(mock_callback)

    # First start
    capture.start()
    thread1 = capture.thread
    pipe_r1 = capture.pipe_r
    pipe_w1 = capture.pipe_w

    # Second start (should be idempotent)
    capture.start()
    assert capture.thread == thread1  # Same thread
    assert capture.pipe_r == pipe_r1  # Same pipe
    assert capture.pipe_w == pipe_w1  # Same pipe

    capture.stop()


def test_global_stream_capture_double_stop():
    """Test that calling stop twice doesn't create issues."""
    mock_callback = MagicMock()
    capture = GlobalStreamCapture(mock_callback)

    capture.start()
    capture.stop()

    # Second stop should be safe
    capture.stop()
    assert capture.capturing is False
    assert capture.thread is None
    # pipe_r is closed by _reader context manager but variable may still hold fd
    # pipe_w should be None
    assert capture.pipe_w is None


def test_global_stream_capture_buffer_output():
    """Test that output is buffered when capture is active."""
    mock_callback = MagicMock()
    capture = GlobalStreamCapture(mock_callback)

    capture.start()

    # Print something while capture is active
    print("Test output 1")
    print("Test output 2")
    sys.stdout.flush()

    # Give reader thread time to process
    time.sleep(0.1)

    # Check buffered output
    buffered = capture.get_buffered_output()
    assert "Test output 1" in buffered
    assert "Test output 2" in buffered

    # Clear buffer
    capture.clear_buffer()
    assert capture.get_buffered_output() == ""

    capture.stop()


def test_global_stream_capture_pause_context_manager():
    """Test the pause context manager."""
    mock_callback = MagicMock()
    capture = GlobalStreamCapture(mock_callback)

    capture.start()

    # Use pause context manager
    with capture.pause():
        # Should be able to print directly to terminal
        print("Direct output")
        sys.stdout.flush()

    # Capture should be active again
    assert capture.capturing is True

    capture.stop()


def test_global_stream_capture_get_original_stdout():
    """Test getting original stdout file object."""
    mock_callback = MagicMock()
    capture = GlobalStreamCapture(mock_callback)

    # Get original stdout before capture starts
    original_stdout = capture.get_original_stdout()
    assert original_stdout is not None
    assert hasattr(original_stdout, "write")
    assert hasattr(original_stdout, "close")

    # Write to it
    original_stdout.write("Test\n")
    original_stdout.flush()
    original_stdout.close()

    capture.start()

    # Get another original stdout while capture is active
    original_stdout2 = capture.get_original_stdout()
    original_stdout2.write("Test2\n")
    original_stdout2.flush()
    original_stdout2.close()

    capture.stop()


def test_global_stream_capture_not_capturing_pause():
    """Test pause context manager when not capturing."""
    mock_callback = MagicMock()
    capture = GlobalStreamCapture(mock_callback)

    # Should not raise error when not capturing
    with capture.pause():
        print("Output when not capturing")

    # Start and stop to ensure cleanup
    capture.start()
    capture.stop()


if __name__ == "__main__":
    pytest.main([__file__])
