from __future__ import annotations

import shutil

from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.utterance import Utterance


class LocalCommandBackend(AnySpeechBackend):
    """A local engine that speaks its argument: ``say`` (``-r`` rate) or
    ``espeak-ng`` (``-s`` rate)."""

    def __init__(self, binary: str, rate_flag: str, voice: str, rate: int) -> None:
        self._binary = binary
        self._rate_flag = rate_flag
        self._voice = voice
        self._rate = rate

    @property
    def name(self) -> str:
        return self._binary

    def create_utterance(self, text: str) -> Utterance:
        if shutil.which(self._binary) is None:
            raise RuntimeError(f"{self._binary} not on PATH")
        argv = [self._binary, self._rate_flag, str(self._rate)]
        if self._voice:
            argv += ["-v", self._voice]
        return Utterance(argv + ["--", text])
