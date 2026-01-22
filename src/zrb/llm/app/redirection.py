import os
import sys
import threading
from typing import TextIO


class GlobalStreamCapture:
    def __init__(self, ui_callback):
        self.ui_callback = ui_callback
        self.pipe_r, self.pipe_w = os.pipe()
        # Save original file descriptors
        self.original_stdout_fd = os.dup(sys.stdout.fileno())
        self.original_stderr_fd = os.dup(sys.stderr.fileno())
        self.capturing = False
        self.thread: threading.Thread | None = None

    def start(self):
        if self.capturing:
            return

        self.capturing = True

        # Flush existing buffers to ensure order
        sys.stdout.flush()
        sys.stderr.flush()

        # Redirect stdout (1) and stderr (2) to the write end of the pipe
        os.dup2(self.pipe_w, sys.stdout.fileno())
        os.dup2(self.pipe_w, sys.stderr.fileno())

        # Start the reader thread
        self.thread = threading.Thread(target=self._reader, daemon=True)
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
        os.close(self.pipe_w)

        if self.thread:
            self.thread.join()

        os.close(self.pipe_r)
        os.close(self.original_stdout_fd)
        os.close(self.original_stderr_fd)

    def _reader(self):
        from prompt_toolkit.application import get_app

        with os.fdopen(self.pipe_r, "r", errors="replace", buffering=1) as f:
            for line in f:
                if line:
                    self.ui_callback(line.expandtabs(4), end="")
                    try:
                        get_app().invalidate()
                    except Exception:
                        pass

    def get_original_stdout(self) -> TextIO:
        """Returns a file object connected to the original stdout (terminal)."""
        return os.fdopen(
            self.original_stdout_fd,
            "w",
            encoding="utf-8",
            errors="replace",
            closefd=False,
        )
