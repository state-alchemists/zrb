"""The speaker's tone, heard by emotion2vec+ in the audio of each utterance.

Dictation runs `EmotionDetector` beside the transcriber, on the same audio, so
it hears the tone whichever backend writes the words, and a streamed one too.
The tone reaches the turn as metadata (`InputProvenance.tone`), never as text
in the user's words. On RAVDESS (actors, 180 clips) emotion2vec+ base was
right 97% of the time at ~0.3 s a clip on a CPU.
"""

from __future__ import annotations

import importlib
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from zrb.util.async_thread import run_in_daemon

logger = logging.getLogger(__name__)

#: The emotion2vec labels reported as a tone. Neutral, fearful, disgusted,
#: other and unknown are not.
_EMOTIONS = ("happy", "sad", "angry", "surprised")

#: Classifies one clip, returning emotion2vec's labels and their scores.
Classify = Callable[[object], dict[str, list[object]]]


@dataclass(frozen=True, slots=True)
class Tone:
    """How an utterance sounded, and how sure emotion2vec+ was (0-1)."""

    emotion: str
    score: float


class EmotionDetector:
    """emotion2vec+ (the Hugging Face repo *model*), reporting a tone it hears
    with at least *min_score*."""

    def __init__(
        self,
        model: str = "emotion2vec/emotion2vec_plus_base",
        min_score: float = 0.5,
    ) -> None:
        self._model_repo = model
        self._min_score = min_score
        self._classify: Classify | None = None
        self._loading = threading.Lock()
        self._is_unavailable = False

    async def prepare(self) -> None:
        """Load the model before the first utterance."""
        await run_in_daemon(self._get_classify, name="zrb-emotion")

    async def hear(self, audio: bytes) -> Tone | None:
        """The tone of *audio* (16 kHz mono 16-bit PCM), or ``None`` when it
        is not one reported, not confident, or the model cannot load."""
        return await run_in_daemon(self._hear, audio, name="zrb-emotion")

    def _hear(self, audio: bytes) -> Tone | None:
        classify = self._get_classify()
        if classify is None or not audio:
            return None
        # lazy: heavy third-party — numpy comes with the voice extra.
        import numpy as np

        samples = np.frombuffer(audio, dtype="<i2").astype("float32") / 32768
        try:
            with self._loading:
                result = classify(samples)
            scores = [float(str(score)) for score in result["scores"]]
            best = max(range(len(scores)), key=scores.__getitem__)
            emotion = str(result["labels"][best]).split("/")[-1]
        except (RuntimeError, ValueError, KeyError, IndexError, TypeError) as exc:
            # Keep dictating; this utterance just has no tone.
            logger.warning(f"Hearing the tone failed: {exc}")
            return None
        if emotion not in _EMOTIONS or scores[best] < self._min_score:
            return None
        return Tone(emotion, round(scores[best], 2))

    def _get_classify(self) -> Classify | None:
        with self._loading:
            if self._classify is None and not self._is_unavailable:
                try:
                    self._classify = _load(self._model_repo)
                except (ImportError, OSError, RuntimeError, ValueError) as exc:
                    # Keep dictating, without tones.
                    self._is_unavailable = True
                    logger.warning(
                        f"Emotion detection is off: {exc}. It needs funasr and "
                        "torch: pip install funasr torch"
                    )
            return self._classify


def _load(repo: str) -> Classify:
    # lazy: heavy third-party — huggingface_hub. funasr and torch are not zrb
    # dependencies, so funasr is imported by name.
    from huggingface_hub import snapshot_download

    auto_model = importlib.import_module("funasr").AutoModel
    model = auto_model(model=snapshot_download(repo), disable_update=True)
    return lambda samples: model.generate(
        samples, granularity="utterance", extract_embedding=False
    )[0]
