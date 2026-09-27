from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile

from zrb.config.config import CFG

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

    def play(self, timeout: float | None) -> None:
        """Play to the end, or stop after *timeout* seconds."""
        subprocess.run(
            self.argv,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )

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
