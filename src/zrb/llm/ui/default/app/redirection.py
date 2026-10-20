import os
import sys
import threading
from contextlib import contextmanager
from typing import TextIO

from zrb.config.config import CFG
from zrb.util.cli.style import is_color_enabled, set_color_enabled

# The captured pipe's reader only reaches EOF once every copy of the write end
# closes; a child spawned during the session holds one for its whole lifetime.
_CAPTURE_CLOSE_WAIT_SECONDS = 0.5


class _Handover:
    """Where a reader's output goes once `stop()` stops waiting for it.

    While the caller still has the buffered output to show, what the reader
    gets is held in `lines`: written straight out, it would overtake output
    made while the session was still running.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.enabled = False
        self.released = False
        self.lines: list[str] = []


class GlobalStreamCapture:
    def __init__(self):
        self.original_stdout_fd = os.dup(sys.stdout.fileno())
        self.original_stderr_fd = os.dup(sys.stderr.fileno())
        # Both directions of the pipe belong to the stream this capture renders
        # back to: a cp1252 console hands us cp1252 bytes and reads cp1252 back,
        # so decoding or re-encoding as UTF-8 loses every character above 127.
        self.terminal_encoding = sys.stdout.encoding or "utf-8"
        self.capturing = False
        self.thread: threading.Thread | None = None
        self.pipe_r = None
        self.pipe_w = None
        self._buffer: list[str] = []
        self._handover: _Handover | None = None

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

        # Per run: a reader left behind by an earlier run keeps its own handover,
        # so a later `start()` still buffers instead of printing straight out.
        self._handover = _Handover()
        self.thread = threading.Thread(
            target=self._reader, args=(self.pipe_r, self._handover), daemon=True
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
            # A child spawned while capturing inherits FD 1/2, so a copy of the
            # write end outlives this call and the reader reaches no EOF. That
            # child is reaped later, in the session teardown, so an unbounded
            # join puts the whole quit behind its lifetime.
            self.thread.join(_CAPTURE_CLOSE_WAIT_SECONDS)
            if self.thread.is_alive():
                # The caller still has the buffer to show, so what the lingering
                # writer emits waits its turn rather than overtaking it.
                if self._handover is not None:
                    with self._handover.lock:
                        self._handover.enabled = True
                CFG.LOGGER.info(
                    "A writer still held the captured pipe after %ss; "
                    "its later output follows the captured output.",
                    _CAPTURE_CLOSE_WAIT_SECONDS,
                )
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

    def _reader(self, pipe_r, handover: _Handover):
        with os.fdopen(
            pipe_r,
            "r",
            encoding=self.terminal_encoding,
            errors="replace",
            buffering=1,
        ) as f:
            for line in f:
                if not line:
                    continue
                with handover.lock:
                    if not handover.enabled:
                        self._buffer.append(line.expandtabs(4))
                        continue
                    if not handover.released:
                        handover.lines.append(line.expandtabs(4))
                        continue
                self._write_to_terminal(line)

    def _write_to_terminal(self, text: str) -> None:
        """Through the FD this capture was made against, not `sys.stdout`: after
        a later `start()`, that points at the new capture's pipe."""
        data = text.encode(self.terminal_encoding, "replace")
        while data:
            try:
                written = os.write(self.original_stdout_fd, data)
            except OSError:
                return
            if written <= 0:
                return
            data = data[written:]

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
        """Returns every line captured up to `stop()`; what a lingering writer
        emits after that is shown by `show_buffered_output()` instead."""
        return "".join(self._buffer)

    def show_buffered_output(self) -> None:
        """Print the captured output, then whatever the lingering writer already
        emitted, and from then on print its output as it arrives."""
        handover = self._handover
        if handover is None:
            self._write_to_terminal("".join(self._buffer))
            return
        with handover.lock:
            text = "".join(self._buffer) + "".join(handover.lines)
            handover.lines.clear()
            self._write_to_terminal(text)
            handover.released = True
