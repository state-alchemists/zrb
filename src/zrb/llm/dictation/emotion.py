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
        # Guards the three fields around it. The load runs on a thread of its
        # own, so `close` can land in the middle of it: without this, the thread
        # publishes a child nobody will ask anything, and it stays resident for
        # the rest of the chat.
        self._state = threading.Lock()
        self._is_closed = False
        # Set by `begin_loading`, before the task that performs the load gets
        # to run: a clip heard in that window is a clip heard while the model
        # loads, so it takes no tone rather than taking on the load itself.
        self._is_preparing = False
        # Guards loading the model. Taken without waiting: an utterance heard
        # while the model loads gets no tone rather than waiting for it.
        self._loading = threading.Lock()
        # Guards every call into the model, which is one model, one clip at a
        # time.
        self._model_lock = threading.Lock()
        self._unavailable_reason = ""

    def begin_loading(self) -> None:
        """Say the model is about to load, before the task that loads it runs.

        A session schedules the load and opens the microphone without waiting
        for either, so the first utterance can arrive before the loading thread
        exists. Without this mark, that utterance takes the load lock first and
        waits out the whole 8–20 s load, which is what the microphone was moved
        off in the first place (ADR-0115)."""
        with self._state:
            if not self._is_closed:
                self._is_preparing = True

    async def prepare(self, report: Callable[[str], None]) -> None:
        """Load the model before the first utterance, through *report*
        saying so when it is not loaded yet."""
        if self._is_closed:
            return
        self.begin_loading()
        try:
            if self._classify is None and not self._unavailable_reason:
                report("Loading the emotion model…")
            await run_in_daemon(self._load, name="zrb-emotion")
        finally:
            with self._state:
                self._is_preparing = False

    @property
    def unavailable_reason(self) -> str:
        """Why the model could not load, so no tone is heard; ``""`` while it
        is loaded or not tried yet."""
        return self._unavailable_reason

    @property
    def is_loading(self) -> bool:
        """Whether the model is loading right now: a tone asked for now is
        none, rather than a wait for the load to finish."""
        return self._loading.locked() or self._is_preparing

    async def hear(self, audio: bytes) -> Tone | None:
        """The tone of *audio* (16 kHz mono 16-bit PCM), or ``None`` when it
        is not one reported, not confident, still loading, or the model cannot
        load."""
        return await run_in_daemon(self._hear, audio, name="zrb-emotion")

    def close(self) -> None:
        """Stop the worker process that held the model, if there is one.

        A load still running is not waited for: it finds the detector closed
        when it lands and closes the worker it made, rather than keeping a child
        nobody can reach for the rest of the chat.
        """
        with self._state:
            self._is_closed = True
            worker, self._worker = self._worker, None
            self._classify = None
        if worker is not None:
            worker.close()

    def _hear(self, audio: bytes) -> Tone | None:
        if self._is_closed:
            # A clip still arriving as the session ends: nothing to ask, and no
            # failure to report for a worker that was stopped on purpose.
            return None
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
        """What a clip uses: the model when it is loaded, and a load of its own
        only when nobody asked for one — a clip heard while a load is on its way
        takes no tone rather than taking the load on itself."""
        if self._is_preparing:
            return None
        return self._load()

    def _load(self) -> Classify | None:
        """The model's classify callable, loading it when this thread is the
        one to, and ``None`` when it is not loaded yet."""
        if self._is_closed:
            return None
        classify = self._loaded()
        if classify is not None or self._unavailable_reason:
            return classify
        if not self._loading.acquire(blocking=False):
            # Another thread is loading it: no tone this time, no wait either.
            return None
        try:
            if self._is_closed:
                return None
            if self._loaded() is None and not self._unavailable_reason:
                try:
                    self._create_classify()
                except MODEL_ERRORS as exc:
                    if self._is_closed:
                        # The session ended while the model loaded: nothing is
                        # off, there is just no tone left to hear.
                        return None
                    # Keep dictating, without tones.
                    self._unavailable_reason = _why_unavailable(exc)
                    logger.warning(
                        f"Emotion detection is off: {self._unavailable_reason}"
                    )
            return self._loaded()
        finally:
            self._loading.release()

    def _loaded(self) -> Classify | None:
        """The callable kept for later clips, or ``None`` when there is none to
        use — a closed detector, or a child that has died since.

        A dead child is discovered here rather than in the call itself: the
        callable a worker hands out talks to a pipe that is gone, so keeping it
        would cost every later clip a failure and never start another child
        (ADR-0115). Dropping it lets the next clip start one, up to
        `MAX_DEATHS`."""
        with self._state:
            if self._is_closed:
                return None
            classify, worker = self._classify, self._worker
        if classify is None:
            return None
        if worker is None or worker.is_started:
            return classify
        self._forget_loaded(classify)
        return None

    def _forget_loaded(self, classify: Classify) -> None:
        """Drop *classify* unless a newer one replaced it meanwhile."""
        with self._state:
            if self._classify is not classify:
                return
            self._classify, self._worker = None, None

    def _publish(self, classify: Classify) -> Classify | None:
        """Keep *classify* for later clips, or ``None`` when this detector was
        closed while the model loaded."""
        with self._state:
            if self._is_closed:
                return None
            self._classify = classify
            return classify

    def _keep_worker(self, worker: EmotionWorker) -> EmotionWorker | None:
        """Keep *worker* from before its model loads, so `close` can stop the
        child a load in progress would otherwise leave behind, or ``None`` when
        this detector was closed first."""
        with self._state:
            if self._is_closed:
                return None
            self._worker = worker
            return worker

    def _create_classify(self) -> None:
        """Load the model, here or in a child process, and keep it for later
        clips unless the detector was closed while it loaded."""
        if not self._out_of_process:
            # Nothing to stop: a model built here goes with this call.
            self._publish(load_classifier(self._model_repo))
            return
        worker = EmotionWorker(self._model_repo)
        if self._keep_worker(worker) is None:
            return
        try:
            classify = worker.start()
        except BaseException:
            worker.close()
            raise
        if self._publish(classify) is None:
            # Closed while the model loaded: `close` stopped this worker, and
            # the second close is the no-op for a child already taken down.
            worker.close()


def _why_unavailable(exc: BaseException) -> str:
    """Why the model is not there, in words that say what to install when the
    package is what is missing."""
    reason = str(exc) or type(exc).__name__
    if isinstance(exc, ImportError):
        return f"{reason}. It needs funasr and torch: pip install funasr torch"
    return reason
