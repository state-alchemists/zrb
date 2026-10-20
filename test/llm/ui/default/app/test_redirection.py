import os
import subprocess
import sys
import threading
import time
from unittest.mock import MagicMock

import pytest

from zrb.llm.ui.default.app.redirection import GlobalStreamCapture


def test_global_stream_capture_initialization():
    """Test GlobalStreamCapture initialization."""
    capture = GlobalStreamCapture()

    assert capture.capturing is False
    assert capture.thread is None
    assert capture.pipe_r is None
    assert capture.pipe_w is None
    # Test buffer through public API
    assert capture.get_buffered_output() == ""
    assert hasattr(capture, "original_stdout_fd")
    assert hasattr(capture, "original_stderr_fd")


def test_global_stream_capture_start_stop():
    """Test starting and stopping capture."""
    capture = GlobalStreamCapture()

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
    capture = GlobalStreamCapture()

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
    capture = GlobalStreamCapture()

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
    capture = GlobalStreamCapture()

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

    capture.stop()


def test_global_stream_capture_pause_context_manager():
    """Test the pause context manager."""
    capture = GlobalStreamCapture()

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
    capture = GlobalStreamCapture()

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
    capture = GlobalStreamCapture()

    # Should not raise error when not capturing
    with capture.pause():
        print("Output when not capturing")

    # Start and stop to ensure cleanup
    capture.start()
    capture.stop()


def test_stop_returns_while_another_writer_still_holds_the_pipe():
    """A child spawned while capturing inherits FD 1/2, so a copy of the pipe's
    write end outlives stop(); the reader sees no EOF until that copy closes."""
    capture = GlobalStreamCapture()
    capture.start()
    write_end = capture.pipe_w
    assert write_end is not None
    held_writer = os.dup(write_end)
    stopper = threading.Thread(target=capture.stop)
    try:
        stopper.start()
        stopper.join(2.0)
        assert not stopper.is_alive(), "stop() waited for the other writer"
    finally:
        os.close(held_writer)
        stopper.join(5.0)


# The teardown sequence under either implementation: stop, take the snapshot,
# print it. Probes replay it so a red run shows the wrong output, not an
# AttributeError on a method the fix adds.
_TEARDOWN = """
if hasattr(capture, "show_buffered_output"):
    capture.show_buffered_output()
else:
    buffered = capture.get_buffered_output()
    if buffered:
        sys.stdout.write(buffered)
        sys.stdout.flush()
"""

_LATE_OUTPUT_PROBE = (
    """
import os
import sys
import time

from zrb.llm.ui.default.app.redirection import GlobalStreamCapture

capture = GlobalStreamCapture()
capture.start()
held = os.dup(capture.pipe_w)
capture.stop()
os.write(held, b"late output\\n")
os.close(held)
"""
    + _TEARDOWN
    + """
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    sys.stdout.flush()
    with open("out.txt", encoding="utf-8") as seen:
        if "late output" in seen.read():
            sys.exit(0)
    time.sleep(0.05)
sys.exit(1)
"""
)

_ORDERING_PROBE = (
    """
import os
import sys
import time

from zrb.llm.ui.default.app.redirection import GlobalStreamCapture

capture = GlobalStreamCapture()
capture.start()
held = os.dup(capture.pipe_w)
sys.stdout.write("before\\n")
sys.stdout.flush()
time.sleep(0.3)
capture.stop()
os.write(held, b"late\\n")
time.sleep(0.5)
"""
    + _TEARDOWN
    + """
os.close(held)
time.sleep(0.2)
"""
)

_RESTART_PROBE = (
    """
import os
import sys
import time

from zrb.llm.ui.default.app.redirection import GlobalStreamCapture

capture = GlobalStreamCapture()
capture.start()
held = os.dup(capture.pipe_w)
capture.stop()
"""
    + _TEARDOWN
    + """
capture.start()
os.write(held, b"old writer\\n")
os.close(held)
time.sleep(0.5)
second = capture.get_buffered_output()
capture.stop()
with open("result.txt", "w", encoding="utf-8") as f:
    f.write("captured again" if "old writer" in second else "on the terminal")
"""
)


_ENCODING_PROBE = (
    """
import os
import sys
import time

from zrb.llm.ui.default.app.redirection import GlobalStreamCapture

capture = GlobalStreamCapture()
capture.start()
held = os.dup(capture.pipe_w)
sys.stdout.write("caf\\u00e9 captured\\n")
sys.stdout.flush()
time.sleep(0.3)
capture.stop()
os.write(held, "caf\\u00e9 late\\n".encode("cp1252"))
os.close(held)
"""
    + _TEARDOWN
    + """
time.sleep(0.3)
"""
)


def _run_probe(probe, tmp_path, env=None):
    stdout_path = tmp_path / "out.txt"
    with open(stdout_path, "wb") as out:
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=tmp_path,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return stdout_path.read_bytes()


def test_output_written_after_the_stop_still_reaches_the_terminal(tmp_path):
    """Late output from the writer stop() stopped waiting for must not vanish:
    the snapshot cannot hold it, so it follows the snapshot instead."""
    assert b"late output" in _run_probe(_LATE_OUTPUT_PROBE, tmp_path)


def test_output_of_a_lingering_writer_follows_the_snapshot(tmp_path):
    """`stop()` hands over while the caller still has the buffered output to
    print, so a late line must wait for that print instead of overtaking it."""
    shown = _run_probe(_ORDERING_PROBE, tmp_path)
    assert b"before" in shown and b"late" in shown
    assert shown.index(b"before") < shown.index(b"late")


def test_the_output_is_written_in_the_encoding_of_the_terminal(tmp_path):
    """The stream this capture renders back to decides the bytes, on the way in
    from the pipe and on the way out: a cp1252 console gets cp1252, not UTF-8."""
    env = dict(os.environ, PYTHONIOENCODING="cp1252:replace")
    shown = _run_probe(_ENCODING_PROBE, tmp_path, env)
    assert shown.count(b"caf\xe9") == 2
    assert b"caf\xc3\xa9" not in shown


def test_a_reader_left_from_an_earlier_capture_writes_to_the_terminal(tmp_path):
    """A later `start()` points FD 1 at a new pipe; the older reader still
    holds the terminal it was made against, so its output is not captured
    again as the new session's."""
    _run_probe(_RESTART_PROBE, tmp_path)
    assert (tmp_path / "result.txt").read_text(encoding="utf-8") == "on the terminal"


if __name__ == "__main__":
    pytest.main([__file__])


_COLOR_PROBE = """
from zrb.llm.ui.default.app.redirection import GlobalStreamCapture
from zrb.util.cli.style import is_color_enabled

capture = GlobalStreamCapture()
capture.start()
during = is_color_enabled()
capture.stop()
with open("result.txt", "w", encoding="utf-8") as f:
    f.write(f"{during} {is_color_enabled()}")
"""


@pytest.mark.skipif(not hasattr(os, "openpty"), reason="needs a pseudo-terminal")
def test_capture_keeps_colour_for_a_terminal_it_renders_back_to(tmp_path):
    """FD 1/2 point at a pipe while capturing, but the output still reaches the
    terminal, so styling must stay on."""
    leader, follower = os.openpty()
    env = {k: v for k, v in os.environ.items() if k not in ("NO_COLOR", "FORCE_COLOR")}
    try:
        subprocess.run(
            [sys.executable, "-c", _COLOR_PROBE],
            cwd=tmp_path,
            env=env,
            stdin=follower,
            stdout=follower,
            stderr=follower,
            timeout=60,
            check=True,
        )
    finally:
        os.close(follower)
        os.close(leader)
    assert (tmp_path / "result.txt").read_text(encoding="utf-8") == "True True"
