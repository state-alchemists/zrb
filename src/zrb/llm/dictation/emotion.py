"""The speaker's tone, heard by emotion2vec+ in the audio of each utterance.

Dictation runs `EmotionDetector` beside the transcriber, on the same audio, so
it hears the tone whichever backend writes the words, and a streamed one too.
The tone reaches the turn as metadata (`InputProvenance.tone`), never as text
in the user's words. Why emotion2vec+ and not the transcriber's own tag:
ADR-0112.

The model is loaded on a thread of its own, without holding up the microphone
(ADR-0115): a tone heard a couple of turns later is worth more than a
microphone that opens twenty seconds late. An utterance spoken while it loads
carries no tone, which is exactly what an utterance spoken before the model
loaded always got.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from zrb.llm.dictation.emotion_model import (
    MODEL_ERRORS,
    Classify,
    EmotionWorker,
    load_classifier,
)
from zrb.util.async_thread import run_in_daemon

logger = logging.getLogger(__name__)

#: The emotion2vec labels reported as a tone. Neutral, fearful, disgusted,
#: other and unknown are not.
_EMOTIONS = ("happy", "sad", "angry", "surprised")


@dataclass(frozen=True, slots=True)
class Tone:
    """How an utterance sounded, and how sure emotion2vec+ was (0-1)."""

    emotion: str
    score: float


class EmotionDetector:
    """emotion2vec+ (the Hugging Face repo *model*), reporting a tone it hears
    with at least *min_score*; ``None`` takes the default of each.

    With *out_of_process*, the model loads in a child process of its own, where
    its load spike cannot cost the chat its life (ADR-0115); without it, the
    model loads in this process.
    """

    def __init__(
        self,
        model: str | None = None,
        min_score: float | None = None,
        out_of_process: bool = False,
    ) -> None:
        self._model_repo = model or "emotion2vec/emotion2vec_plus_base"
        self._min_score = 0.5 if min_score is None else min_score
        self._out_of_process = out_of_process
        self._classify: Classify | None = None
        self._worker: EmotionWorker | None = None
        # Guards loading the model. Taken without waiting: an utterance heard
        # while the model loads gets no tone rather than waiting for it.
        self._loading = threading.Lock()
        # Guards every call into the model, which is one model, one clip at a
        # time.
        self._model_lock = threading.Lock()
        self._unavailable_reason = ""

    async def prepare(self, report: Callable[[str], None]) -> None:
        """Load the model before the first utterance, through *report*
        saying so when it is not loaded yet."""
        if self._classify is None and not self._unavailable_reason:
            report("Loading the emotion model…")
        await run_in_daemon(self._get_classify, name="zrb-emotion")

    @property
    def unavailable_reason(self) -> str:
        """Why the model could not load, so no tone is heard; ``""`` while it
        is loaded or not tried yet."""
        return self._unavailable_reason

    @property
    def is_loading(self) -> bool:
        """Whether the model is loading right now: a tone asked for now is
        none, rather than a wait for the load to finish."""
        return self._loading.locked()

    async def hear(self, audio: bytes) -> Tone | None:
        """The tone of *audio* (16 kHz mono 16-bit PCM), or ``None`` when it
        is not one reported, not confident, still loading, or the model cannot
        load."""
        return await run_in_daemon(self._hear, audio, name="zrb-emotion")

    def close(self) -> None:
        """Stop the worker process that held the model, if there is one."""
        worker, self._worker = self._worker, None
        self._classify = None
        if worker is not None:
            worker.close()

    def _hear(self, audio: bytes) -> Tone | None:
        classify = self._get_classify()
        if classify is None or not audio:
            return None
        # lazy: heavy third-party — numpy comes with the voice extra.
        import numpy as np

        samples = np.frombuffer(audio, dtype="<i2").astype("float32") / 32768
        try:
            with self._model_lock:
                result = classify(samples)
            scores = [float(str(score)) for score in result["scores"]]
            best = max(range(len(scores)), key=scores.__getitem__)
            emotion = str(result["labels"][best]).split("/")[-1]
        except MODEL_ERRORS as exc:
            # Keep dictating; this utterance just has no tone.
            logger.warning(f"Hearing the tone failed: {exc}")
            return None
        if emotion not in _EMOTIONS or scores[best] < self._min_score:
            return None
        return Tone(emotion, round(scores[best], 2))

    def _get_classify(self) -> Classify | None:
        """The model's classify callable, loading it when this thread is the
        one to, and ``None`` when it is not loaded yet."""
        if self._classify is not None or self._unavailable_reason:
            return self._classify
        if not self._loading.acquire(blocking=False):
            # Another thread is loading it: no tone this time, no wait either.
            return None
        try:
            if self._classify is None and not self._unavailable_reason:
                try:
                    self._classify = self._create_classify()
                except MODEL_ERRORS as exc:
                    # Keep dictating, without tones.
                    self._unavailable_reason = _why_unavailable(exc)
                    logger.warning(
                        f"Emotion detection is off: {self._unavailable_reason}"
                    )
            return self._classify
        finally:
            self._loading.release()

    def _create_classify(self) -> Classify:
        """The classify callable, from a child process or from this one."""
        if not self._out_of_process:
            return load_classifier(self._model_repo)
        worker = EmotionWorker(self._model_repo)
        try:
            classify = worker.start()
        except BaseException:
            worker.close()
            raise
        self._worker = worker
        return classify


def _why_unavailable(exc: BaseException) -> str:
    """Why the model is not there, in words that say what to install when the
    package is what is missing."""
    reason = str(exc) or type(exc).__name__
    if isinstance(exc, ImportError):
        return f"{reason}. It needs funasr and torch: pip install funasr torch"
    return reason
