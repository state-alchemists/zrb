"""Direct tests for the hook pipe reader.

The realistic paths — a chatty child, a disowned descendant holding the pipes,
a timeout — are driven end-to-end through `create_command_hook` in
`test_creator_subprocess.py`. What is left here is the handful of degenerate
pipe states a real subprocess will not reliably produce on demand.
"""

import os

from zrb.llm.hook.process_io import read_hook_output


class _FakePipe:
    """A read/write end of a real OS pipe, with an optionally failing close()."""

    def __init__(self, fd, close_error=None):
        self._fd = fd
        self._close_error = close_error
        self.close_calls = 0

    def fileno(self):
        return self._fd

    def close(self):
        self.close_calls += 1
        if self._close_error is not None:
            raise self._close_error
        try:
            os.close(self._fd)
        except OSError:
            pass


class _FakeProc:
    """An already-exited process whose streams are real pipes."""

    def __init__(self, stdout=b"", stderr=b"", stdin=False, close_error=None):
        self.stdout = self._readable(stdout)
        self.stderr = self._readable(stderr, close_error=close_error)
        self.stdin = None
        if stdin:
            # Hold the read end open so a write cannot EPIPE.
            self.stdin_r, stdin_w = os.pipe()
            self.stdin = _FakePipe(stdin_w)
        self.returncode = 0

    @staticmethod
    def _readable(data, close_error=None):
        read_fd, write_fd = os.pipe()
        if data:
            os.write(write_fd, data)
        os.close(write_fd)  # immediate EOF after any buffered data
        return _FakePipe(read_fd, close_error=close_error)

    def poll(self):
        return self.returncode

    def wait(self):
        return self.returncode


def test_read_hook_output_collects_both_streams_to_eof():
    """Whatever the child wrote before exiting is returned in full."""
    process = _FakeProc(stdout=b"out-payload", stderr=b"err-payload")

    stdout, stderr = read_hook_output(process, b"")

    assert stdout == b"out-payload"
    assert stderr == b"err-payload"


def test_read_hook_output_closes_stdin_when_there_is_nothing_to_send():
    """An empty payload closes stdin immediately rather than registering it.

    A hook reading stdin must see EOF, not block forever waiting on a write that
    is never coming.
    """
    process = _FakeProc(stdout=b"ok", stdin=True)

    stdout, _ = read_hook_output(process, b"")

    assert stdout == b"ok"
    assert process.stdin.close_calls >= 1


def test_read_hook_output_delivers_the_stdin_payload():
    """A non-empty payload is written to the child before the reader finishes."""
    process = _FakeProc(stdout=b"ok", stdin=True)

    stdout, _ = read_hook_output(process, b'{"hook_event_name": "Notification"}')

    assert stdout == b"ok"
    # The child's read end still holds what was written.
    assert b"Notification" in os.read(process.stdin_r, 4096)


class _ProcThatExitsAfterTheFirstPoll:
    """A child that finishes and flushes between the first select and the poll.

    The shape of every fast hook: `echo hello` is spawned, the selector wakes
    immediately because *stdin* is writable (it always is), and by the time
    `poll()` is asked the child has already run, written, and exited.
    """

    def __init__(self):
        stdout_r, self._stdout_w = os.pipe()
        stderr_r, self._stderr_w = os.pipe()
        self.stdin_r, stdin_w = os.pipe()
        self.stdout = _FakePipe(stdout_r)
        self.stderr = _FakePipe(stderr_r)
        self.stdin = _FakePipe(stdin_w)
        self.returncode = 0
        self._exited = False

    def poll(self):
        if not self._exited:
            self._exited = True
            os.write(self._stdout_w, b"hello-context")
            os.close(self._stdout_w)
            os.close(self._stderr_w)
        return self.returncode

    def wait(self):
        return self.returncode


def test_read_hook_output_does_not_drop_a_child_that_exits_in_the_first_poll():
    """A poll that only saw stdin writable is not a quiet interval.

    The exit test used to be "this poll read nothing", and stdin is writable
    from the moment the child is spawned — so a child that exited during the
    first poll had its output discarded unread. `echo hello-context` lost its
    line often enough to make the hook suite flaky, and a SessionStart hook
    silently contributed no context at all.
    """
    process = _ProcThatExitsAfterTheFirstPoll()

    stdout, _ = read_hook_output(process, b'{"hook_event_name": "SessionStart"}')

    assert stdout == b"hello-context"


def test_read_hook_output_survives_a_pipe_that_fails_to_close():
    """A close() that raises must not escape.

    The reader runs on a detached thread whose exception becomes the hook's
    result, so a failure here would turn a hook that ran fine into an error.
    """
    process = _FakeProc(
        stdout=b"fine", stderr=b"", close_error=RuntimeError("close failed")
    )

    stdout, stderr = read_hook_output(process, b"")

    assert stdout == b"fine"
    assert stderr == b""
    assert process.stderr.close_calls >= 1
