import os
import sys
import threading
from contextlib import contextmanager
from typing import TextIO

from zrb.util.cli.style import is_color_enabled, set_color_enabled


class GlobalStreamCapture:
    def __init__(self):
        self.original_stdout_fd = os.dup(sys.stdout.fileno())
        self.original_stderr_fd = os.dup(sys.stderr.fileno())
        self.capturing = False
        self.thread: threading.Thread | None = None
        self.pipe_r = None
        self.pipe_w = None
        self._buffer: list[str] = []

    def start(self):
        if self.capturing:
            return

        self.capturing = True

        self.pipe_r, self.pipe_w = os.pipe()

        # FD 1/2 become a pipe, but what is written there is still shown on
        # this terminal, so keep the colour decision made before the swap.
        set_color_enabled(is_color_enabled())
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(self.pipe_w, sys.stdout.fileno())
        os.dup2(self.pipe_w, sys.stderr.fileno())

        self.thread = threading.Thread(
            target=self._reader, args=(self.pipe_r,), daemon=True
        )
        self.thread.start()

    def stop(self):
        if not self.capturing:
            return

        self.capturing = False

        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(self.original_stdout_fd, sys.stdout.fileno())
        os.dup2(self.original_stderr_fd, sys.stderr.fileno())
        set_color_enabled(None)

        # Closing the write end signals EOF; the reader closes pipe_r.
        if self.pipe_w is not None:
            os.close(self.pipe_w)
            self.pipe_w = None

        if self.thread:
            self.thread.join()
            self.thread = None

    @contextmanager
    def pause(self):
        """Point FD 1/2 back at the terminal for a subprocess (e.g. vim),
        keeping the pipe and reader thread alive."""
        if not self.capturing:
            yield
            return

        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(self.original_stdout_fd, sys.stdout.fileno())
        os.dup2(self.original_stderr_fd, sys.stderr.fileno())

        try:
            yield
        finally:
            if self.pipe_w is not None:
                sys.stdout.flush()
                sys.stderr.flush()
                os.dup2(self.pipe_w, sys.stdout.fileno())
                os.dup2(self.pipe_w, sys.stderr.fileno())

    def _reader(self, pipe_r):
        with os.fdopen(pipe_r, "r", errors="replace", buffering=1) as f:
            for line in f:
                if line:
                    self._buffer.append(line.expandtabs(4))

    def get_original_stdout(self) -> TextIO:
        """Returns a file object connected to the original stdout (terminal)."""
        if os.name == "nt":
            try:
                # CONOUT$ is more robust than duping a redirected FD 1.
                return open("CONOUT$", "w", encoding="utf-8", errors="replace")
            except Exception:
                # Fall through to the portable os.dup.
                pass
        new_fd = os.dup(self.original_stdout_fd)
        return os.fdopen(
            new_fd,
            "w",
            encoding="utf-8",
            errors="replace",
            closefd=True,
        )

    def get_buffered_output(self) -> str:
        """Returns all buffered output as a single string."""
        return "".join(self._buffer)
