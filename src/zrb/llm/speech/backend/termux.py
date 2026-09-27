from __future__ import annotations

import shutil

from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.utterance import Utterance


class TermuxSpeechBackend(AnySpeechBackend):
    """Android's text-to-speech through Termux:API's `termux-tts-speak`.

    Each argument maps to one of its flags: *language* ``-l``, *voice_name*
    ``-v`` (variant), *engine* ``-e``, *region* ``-n``, *rate* ``-r`` (1.0 is
    normal speed), *pitch* ``-p`` (1.0 is normal), *stream* ``-s``.
    """

    def __init__(
        self,
        language: str | None = None,
        voice_name: str | None = None,
        engine: str | None = None,
        region: str | None = None,
        rate: float | None = None,
        pitch: float | None = None,
        stream: str | None = None,
    ) -> None:
        self._flags = (
            ("-l", language),
            ("-e", engine),
            ("-n", region),
            ("-v", voice_name),
            ("-r", rate),
            ("-p", pitch),
            ("-s", stream),
        )

    @property
    def name(self) -> str:
        return "termux"

    def create_command(self, text: str) -> list[str]:
        """The `termux-tts-speak` argv that says *text*."""
        argv = ["termux-tts-speak"]
        for flag, value in self._flags:
            if value:
                argv += [flag, str(value)]
        return argv + [text]

    def create_utterance(self, text: str) -> Utterance:
        if shutil.which("termux-tts-speak") is None:
            raise RuntimeError(
                "termux-tts-speak not on PATH: pkg install termux-api, and "
                "install the Termux:API app"
            )
        return Utterance(self.create_command(text))
