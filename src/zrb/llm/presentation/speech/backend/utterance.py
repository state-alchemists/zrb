from __future__ import annotations

import logging
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from typing import BinaryIO

from zrb.config.config import CFG

logger = logging.getLogger(__name__)

_WAV_PLAYERS = (
    ["afplay"],
    ["paplay"],
    ["aplay", "-q"],
    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
)
# The WAV players that read standard input when given no file.
_STREAM_PLAYERS = (
    ["paplay"],
    ["aplay", "-q"],
    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-"],
)


class Utterance:
    """Speech ready to play: the player command, plus a temp file to delete.

    A backend that plays audio some other way returns a subclass overriding
    `play` (and `cleanup`, if it has something to release); its `play`
    calls `report_started` once sound starts.
    """

    def __init__(self, argv: list[str], temp_path: str | None = None):
        self.argv = argv
        self.temp_path = temp_path
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._is_stopped = False
        self._on_start: Callable[[], None] | None = None

    def play(self, timeout: float | None) -> None:
        """Play to the end, or until *timeout* seconds or `stop`."""
        with self._lock:
            if self._is_stopped:
                return
            process = self._process = self.open_player()
        self.report_started()
        try:
            self.feed_player(process)
            returncode = process.wait(timeout)
        except subprocess.TimeoutExpired:
            self.stop()
            return
        except BaseException:
            self.stop()
            raise
        if returncode != 0 and not self._is_stopped:
            logger.warning(f"Speech player {self.argv[0]} exited with {returncode}")

    def set_on_start(self, on_start: Callable[[], None] | None) -> None:
        """Call *on_start* once, when playback starts: the player started, or
        the audio device opened. Never for speech that does not play."""
        self._on_start = on_start

    def report_started(self) -> None:
        """Playback has started: call the `set_on_start` callback, once."""
        on_start, self._on_start = self._on_start, None
        if on_start is not None:
            on_start()

    def open_player(self) -> "subprocess.Popen[bytes]":
        return subprocess.Popen(
            self.argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    def feed_player(self, process: "subprocess.Popen[bytes]") -> None:
        """Hand the started player its audio; nothing here, the path is in
        its arguments."""

    @property
    def is_stopped(self) -> bool:
        return self._is_stopped

    @property
    def is_pausable(self) -> bool:
        """Whether `pause` holds playback; a player program cannot."""
        return False

    def pause(self) -> None:
        """Hold playback where it is, when `is_pausable`; else nothing."""

    def resume(self) -> None:
        """Carry on after `pause`."""

    def stop(self) -> None:
        """End playback now, from any thread; a later `play` does nothing."""
        with self._lock:
            self._is_stopped = True
            process = self._process
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()

    def cleanup(self) -> None:
        if self.temp_path:
            try:
                os.remove(self.temp_path)
            except OSError:
                pass


class StreamedUtterance(Utterance):
    """Plays WAV audio as it is read from *source*, piped into a player that
    reads standard input, so playback starts with the first bytes.

    *source* is a response read from a socket, with a read timeout: `stop`
    shuts that socket down to end a stalled read. Any other stream is read
    until it ends or fails on its own.
    """

    def __init__(self, argv: list[str], source: BinaryIO):
        super().__init__(argv)
        self._source = source
        self._pump: threading.Thread | None = None

    def open_player(self) -> "subprocess.Popen[bytes]":
        return subprocess.Popen(
            self.argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def feed_player(self, process: "subprocess.Popen[bytes]") -> None:
        # Pumped on its own thread so the play timeout and `stop` cover the
        # download too: killing the player ends `play` whatever the read does.
        # `stop` shuts down the connection under a stalled read to end it.
        self._pump = threading.Thread(target=self._pump_into, args=(process,))
        self._pump.daemon = True
        self._pump.start()

    def _pump_into(self, process: "subprocess.Popen[bytes]") -> None:
        stdin = process.stdin
        try:
            while stdin and not self.is_stopped and (chunk := self._source.read(8192)):
                stdin.write(chunk)
        except BrokenPipeError:
            pass  # the player exited or was stopped; its exit code tells which
        except (OSError, ValueError) as exc:
            if not self.is_stopped:
                logger.warning(f"Speech stream failed: {exc}")
        finally:
            for stream in (self._source, stdin):
                try:
                    if stream:
                        stream.close()
                except OSError:
                    pass

    def stop(self) -> None:
        super().stop()
        shut_down_socket(self._source)

    def cleanup(self) -> None:
        pump = self._pump
        if pump is None:  # never played; else the pump closes it
            self._source.close()
        else:  # the player may have quit before reading it all; stopping
            # ends the read, and the pump does not report it as a failure
            self.stop()
            pump.join(_PUMP_JOIN_SECONDS)
        super().cleanup()


_PUMP_JOIN_SECONDS = 1.0


def shut_down_socket(source: BinaryIO) -> None:
    """End a read blocked on *source*'s socket, from another thread. Closing
    the reader itself would wait for the read, which holds its lock; a source
    not backed by a socket is left alone.

    The socket is wrapped in place and detached, never closed, so the reader
    keeps its descriptor. It is not duplicated: on Windows the number is a
    socket handle, which `os.dup` rejects."""
    try:
        handle = source.fileno()
        sock = socket.socket(fileno=handle)
    except (OSError, ValueError):
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    finally:
        sock.detach()
    if sys.platform == "win32":
        _cancel_pending_io(handle)


def _cancel_pending_io(handle: int) -> None:
    """Abort a `recv` blocked on *handle*: unlike on POSIX, a shutdown does
    not wake it on Windows, and closing the handle here would leave the
    reader to close it again once the number may belong to another socket."""
    # lazy: platform-only — `ctypes.windll` exists only on Windows, and
    # loading ctypes costs import time the other platforms never use.
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    kernel32.CancelIoEx(ctypes.c_void_p(handle), None)


def create_streamed_wav_utterance(source: BinaryIO, wav_player: str = "") -> Utterance:
    """An utterance playing the WAV read from *source* as it arrives, when a
    player on PATH reads standard input; else, or with a *wav_player* (which
    takes a file path), it is read in full first."""
    if not wav_player:
        for argv in _STREAM_PLAYERS:
            if shutil.which(argv[0]):
                return StreamedUtterance(argv, source)
    with source:
        wav_bytes = source.read()
    return create_wav_utterance(wav_bytes, wav_player)


def create_wav_utterance(wav_bytes: bytes, wav_player: str = "") -> Utterance:
    """An utterance playing *wav_bytes* with *wav_player* (a command line, the
    file path appended), else the first WAV player on PATH."""
    player = shlex.split(wav_player) or _find_wav_player()
    prefix = f"{CFG.ROOT_GROUP_NAME}-speech-"
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as wav_file:
            wav_file.write(wav_bytes)
    except BaseException:
        os.unlink(path)
        raise
    return Utterance(player + [path], temp_path=path)


def _find_wav_player() -> list[str]:
    for argv in _WAV_PLAYERS:
        if shutil.which(argv[0]):
            return argv
    names = ", ".join(argv[0] for argv in _WAV_PLAYERS)
    raise RuntimeError(f"no WAV player on PATH ({names})")
