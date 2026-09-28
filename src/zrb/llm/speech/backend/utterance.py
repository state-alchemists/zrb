from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
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
    `play` (and `cleanup`, if it has something to release).
    """

    def __init__(self, argv: list[str], temp_path: str | None = None):
        self.argv = argv
        self.temp_path = temp_path
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._is_stopped = False

    def play(self, timeout: float | None) -> None:
        """Play to the end, or until *timeout* seconds or `stop`."""
        with self._lock:
            if self._is_stopped:
                return
            process = self._process = self.open_player()
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
    reads standard input, so playback starts with the first bytes."""

    def __init__(self, argv: list[str], source: BinaryIO):
        super().__init__(argv)
        self._source = source

    def open_player(self) -> "subprocess.Popen[bytes]":
        return subprocess.Popen(
            self.argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def feed_player(self, process: "subprocess.Popen[bytes]") -> None:
        # ponytail: the play timeout starts once the audio is all read; a
        # stalled download is bounded by the HTTP timeout on each read.
        stdin = process.stdin
        if stdin is None:
            return
        try:
            while not self.is_stopped and (chunk := self._source.read(8192)):
                stdin.write(chunk)
        except BrokenPipeError:
            pass  # the player exited or was stopped; its exit code tells which
        except OSError as exc:
            if not self.is_stopped:
                logger.warning(f"Speech stream failed: {exc}")
        finally:
            try:
                stdin.close()
            except OSError:
                pass

    def cleanup(self) -> None:
        self._source.close()
        super().cleanup()


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
