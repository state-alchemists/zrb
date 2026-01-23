import os
import sys
import threading
from contextlib import contextmanager
from typing import TextIO


class GlobalStreamCapture:
    def __init__(self, ui_callback):
        self.ui_callback = ui_callback
        # Save original file descriptors once
        self.original_stdout_fd = os.dup(sys.stdout.fileno())
        self.original_stderr_fd = os.dup(sys.stderr.fileno())
        self.capturing = False
        self.thread: threading.Thread | None = None
        self.pipe_r = None
        self.pipe_w = None

    def start(self):
        if self.capturing:
            return

        self.capturing = True

        # Create new pipe for this session
        self.pipe_r, self.pipe_w = os.pipe()

        # Flush existing buffers to ensure order
        sys.stdout.flush()
        sys.stderr.flush()

        # Redirect stdout (1) and stderr (2) to the write end of the pipe
        os.dup2(self.pipe_w, sys.stdout.fileno())
        os.dup2(self.pipe_w, sys.stderr.fileno())

        # Start the reader thread
        self.thread = threading.Thread(
            target=self._reader, args=(self.pipe_r,), daemon=True
        )
        self.thread.start()

    def stop(self):
        if not self.capturing:
            return

        self.capturing = False

        # Restore original file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(self.original_stdout_fd, sys.stdout.fileno())
        os.dup2(self.original_stderr_fd, sys.stderr.fileno())

        # Close the write end of the pipe to signal EOF to the reader
        if self.pipe_w is not None:
            os.close(self.pipe_w)
            self.pipe_w = None

        if self.thread:
            self.thread.join()
            self.thread = None

        # pipe_r is closed by _reader context manager

    @contextmanager
    def pause(self):
        """
        Temporarily restores original file descriptors without tearing down the thread or pipe.
        Use this when handing control of the terminal to a subprocess (e.g. vim).
        """
        if not self.capturing:
            yield
            return

        # 1. Flush Python buffers to ensure everything pending goes to the pipe
        sys.stdout.flush()
        sys.stderr.flush()

        # 2. Restore original FDs (point FD 1/2 back to TTY)
        os.dup2(self.original_stdout_fd, sys.stdout.fileno())
        os.dup2(self.original_stderr_fd, sys.stderr.fileno())

        try:
            yield
        finally:
            # 3. Restore redirection (point FD 1/2 back to pipe)
            if self.pipe_w is not None:
                # Flush again just in case
                sys.stdout.flush()
                sys.stderr.flush()
                os.dup2(self.pipe_w, sys.stdout.fileno())
                os.dup2(self.pipe_w, sys.stderr.fileno())

    def _reader(self, pipe_r):
        from prompt_toolkit.application import get_app

        with os.fdopen(pipe_r, "r", errors="replace", buffering=1) as f:
            for line in f:
                if line:
                    self.ui_callback(line.expandtabs(4), end="")
                    try:
                        get_app().invalidate()
                    except Exception:
                        pass

    def get_original_stdout(self) -> TextIO:
        """Returns a file object connected to the original stdout (terminal)."""
        new_fd = os.dup(self.original_stdout_fd)
        return os.fdopen(
            new_fd,
            "w",
            encoding="utf-8",
            errors="replace",
            closefd=True,
        )
