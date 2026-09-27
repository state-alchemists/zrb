from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import tempfile
import threading

from zrb.config.config import CFG

logger = logging.getLogger(__name__)

_WAV_PLAYERS = (
    ["afplay"],
    ["paplay"],
    ["aplay", "-q"],
    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
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
            process = self._process = subprocess.Popen(
                self.argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        try:
            returncode = process.wait(timeout)
        except subprocess.TimeoutExpired:
            self.stop()
            return
        except BaseException:
            self.stop()
            raise
        if returncode != 0 and not self._is_stopped:
            logger.warning(f"Speech player {self.argv[0]} exited with {returncode}")

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
