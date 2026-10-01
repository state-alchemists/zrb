from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile

from zrb.config.config import CFG
from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.audio import SpeechAudio, create_streamed_wav_audio
from zrb.llm.speech.backend.utterance import Utterance


class LocalCommandBackend(AnySpeechBackend):
    """A local engine that speaks its argument: ``say`` (``-r`` rate) or
    ``espeak-ng`` (``-s`` rate). Rendering audio for zrb to play may take
    *render_timeout* seconds (default: `CFG.LLM_SPEECH_RENDER_TIMEOUT`); a
    sentence takes well under one, so this only bounds an engine that
    hangs."""

    def __init__(
        self,
        binary: str,
        rate_flag: str,
        voice: str,
        rate: int,
        render_timeout: float | None = None,
    ) -> None:
        self._render_timeout = render_timeout
        self._binary = binary
        self._rate_flag = rate_flag
        self._voice = voice
        self._rate = rate

    @property
    def name(self) -> str:
        return self._binary

    def create_utterance(self, text: str) -> Utterance:
        return Utterance(self._create_argv() + ["--", text])

    def create_audio(self, text: str) -> SpeechAudio | None:
        """``say`` renders to a WAV file (``-o``), ``espeak-ng`` to standard
        output (``--stdout``); another binary cannot render."""
        if self._binary == "say":
            return self._render_to_file(text)
        if self._binary == "espeak-ng":
            wav = self._run(self._create_argv() + ["--stdout", "--", text])
            return create_streamed_wav_audio(io.BytesIO(wav))
        return None

    def _render_to_file(self, text: str) -> SpeechAudio:
        prefix = f"{CFG.ROOT_GROUP_NAME}-speech-"
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=".wav")
        os.close(fd)
        try:
            self._run(
                self._create_argv()
                + ["-o", path, "--data-format=LEI16@22050", "--", text]
            )
            with open(path, "rb") as wav_file:
                return create_streamed_wav_audio(io.BytesIO(wav_file.read()))
        finally:
            os.remove(path)

    def _create_argv(self) -> list[str]:
        if shutil.which(self._binary) is None:
            raise RuntimeError(f"{self._binary} not on PATH")
        argv = [self._binary, self._rate_flag, str(self._rate)]
        if self._voice:
            argv += ["-v", self._voice]
        return argv

    def _run(self, argv: list[str]) -> bytes:
        timeout = self._render_timeout
        if timeout is None:
            timeout = CFG.LLM_SPEECH_RENDER_TIMEOUT
        result = subprocess.run(
            argv, capture_output=True, timeout=timeout or None, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{self._binary} exited with {result.returncode}: "
                f"{result.stderr.decode(errors='replace').strip()}"
            )
        return result.stdout
