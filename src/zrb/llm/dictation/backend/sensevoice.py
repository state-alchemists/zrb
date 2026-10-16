"""Offline dictation with SenseVoice on sherpa-onnx, fast on a CPU. The model
is downloaded from Hugging Face on first use. Its own emotion tag is left
unread: on English speech it was right 18% of the time, so the tone comes
from `EmotionDetector` instead."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.util.async_thread import run_in_daemon

if TYPE_CHECKING:
    from sherpa_onnx import OfflineRecognizer

SAMPLE_RATE = 16000


class SenseVoiceDictationBackend(AnyDictationBackend):
    """SenseVoice through sherpa-onnx, from the Hugging Face repo *model*.

    *language* is ``auto`` or one of ``zh``, ``en``, ``ja``, ``ko``, ``yue``."""

    def __init__(
        self,
        model: str = "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17",
        language: str = "",
        num_threads: int = 4,
    ) -> None:
        self._model = model
        self._language = language or "auto"
        self._num_threads = num_threads
        self._recognizer: "OfflineRecognizer | None" = None
        self._loading = threading.Lock()

    @property
    def name(self) -> str:
        return "sensevoice"

    async def prepare(self, report: Callable[[str], None]) -> None:
        """Download and load the model before the first recording."""
        await run_in_daemon(self._get_recognizer, name="zrb-sensevoice")

    async def transcribe(self, audio: bytes) -> str:
        """*audio*'s words."""
        return await run_in_daemon(self._transcribe, audio, name="zrb-sensevoice")

    def _transcribe(self, audio: bytes) -> str:
        # lazy: heavy third-party — numpy comes with the voice extra.
        import numpy as np

        samples = np.frombuffer(audio, dtype="<i2").astype("float32") / 32768
        recognizer = self._get_recognizer()
        stream = recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples)
        recognizer.decode_stream(stream)
        return stream.result.text.strip()

    def _get_recognizer(self) -> "OfflineRecognizer":
        with self._loading:
            if self._recognizer is None:
                self._recognizer = self._create_recognizer()
            return self._recognizer

    def _create_recognizer(self) -> "OfflineRecognizer":
        try:
            # lazy: heavy third-party — sherpa-onnx is installed separately.
            import sherpa_onnx
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            raise RuntimeError(
                "the sensevoice dictation backend needs sherpa-onnx and "
                "huggingface_hub: pip install sherpa-onnx huggingface_hub"
            ) from exc
        return sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=hf_hub_download(self._model, "model.int8.onnx"),
            tokens=hf_hub_download(self._model, "tokens.txt"),
            num_threads=self._num_threads,
            language=self._language,
            use_itn=True,
        )
