"""The speaker's tone: emotion2vec+ beside the transcriber, carried by the turn."""

import asyncio
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.emotion import EmotionDetector, Tone
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import Utterance
from zrb.llm.input_source import DICTATION_INPUT

LABELS = ["生气/angry", "开心/happy", "中立/neutral", "难过/sad", "吃惊/surprised"]


@pytest.fixture
def classifier(monkeypatch):
    """A fake funasr AutoModel scoring every clip as *scores* says."""
    state = SimpleNamespace(
        scores=[0.0, 0.9, 0.1, 0.0, 0.0],
        loaded=[],
        error=None,
        cached=True,
        asked=[],
    )

    class AutoModel:
        def __init__(self, model, disable_update):
            state.loaded.append(model)

        def generate(self, input, granularity, extract_embedding):
            if state.error is not None:
                raise state.error
            return [{"labels": LABELS, "scores": state.scores}]

    monkeypatch.setitem(sys.modules, "funasr", SimpleNamespace(AutoModel=AutoModel))

    def snapshot_download(repo, local_files_only=False):
        state.asked.append(local_files_only)
        if local_files_only and not state.cached:
            raise FileNotFoundError(repo)
        return f"/cache/{repo}"

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(snapshot_download=snapshot_download),
    )
    return state


@pytest.mark.asyncio
async def test_a_cached_model_loads_without_asking_the_hub(classifier):
    await EmotionDetector("me/e2v").prepare(lambda message: None)

    assert classifier.asked == [True]
    assert classifier.loaded == ["/cache/me/e2v"]


@pytest.mark.asyncio
async def test_a_model_not_cached_yet_is_downloaded(classifier):
    classifier.cached = False

    await EmotionDetector("me/e2v").prepare(lambda message: None)

    assert classifier.asked == [True, False]
    assert classifier.loaded == ["/cache/me/e2v"]


@pytest.mark.asyncio
async def test_a_confident_tone_is_heard_with_its_score(classifier):
    detector = EmotionDetector("me/e2v", min_score=0.5)

    assert await detector.hear(b"\x00\x10" * 160) == Tone("happy", 0.9)
    assert classifier.loaded == ["/cache/me/e2v"]


@pytest.mark.asyncio
async def test_an_unsure_or_unreported_tone_is_none(classifier):
    assert await EmotionDetector(min_score=0.95).hear(b"\x00\x00") is None

    classifier.scores = [0.0, 0.0, 0.99, 0.0, 0.0]
    assert await EmotionDetector().hear(b"\x00\x00") is None
    assert await EmotionDetector().hear(b"") is None


@pytest.mark.asyncio
async def test_a_failing_model_hears_no_tone_and_says_why(classifier, caplog):
    classifier.scores = []

    assert await EmotionDetector().hear(b"\x00\x00") is None
    assert "Hearing the tone failed" in caplog.text


@pytest.mark.asyncio
async def test_a_model_raising_an_unexpected_error_costs_only_the_tone(
    classifier, caplog
):
    classifier.error = AssertionError("bad clip")

    assert await EmotionDetector().hear(b"\x00\x00") is None
    assert "bad clip" in caplog.text


@pytest.mark.asyncio
async def test_prepare_loads_the_model_once_and_says_so(classifier):
    detector = EmotionDetector("me/e2v")
    reports: list[str] = []

    await detector.prepare(reports.append)
    await detector.prepare(reports.append)
    await detector.hear(b"\x00\x00")

    assert classifier.loaded == ["/cache/me/e2v"]
    assert reports == ["Loading the emotion model…"]


@pytest.mark.asyncio
async def test_without_funasr_no_tone_is_heard_and_it_says_why_once(
    monkeypatch, caplog
):
    monkeypatch.setitem(sys.modules, "funasr", None)
    detector = EmotionDetector()

    assert await detector.hear(b"\x00\x00") is None
    assert await detector.hear(b"\x00\x00") is None
    assert caplog.text.count("pip install funasr torch") == 1
    assert "pip install funasr torch" in detector.unavailable_reason


@pytest.mark.asyncio
async def test_a_model_that_cannot_load_ends_its_loading_line_with_a_failure(
    monkeypatch, caplog
):
    monkeypatch.setitem(sys.modules, "funasr", None)
    # Fakes the microphone; the real detector then replaces the fake one.
    _session_hearing(monkeypatch, "hello", detect_emotion=True)
    monkeypatch.setattr("zrb.llm.dictation.feature.EmotionDetector", EmotionDetector)
    session = DictationSession(
        DictationConfig(
            backend=WordsBackend(), mode="hands_free", detect_emotion=True
        ).resolve()
    )

    assert await _sources(session, 1) == [("hello", DICTATION_INPUT)]
    assert "Loading the emotion model…" in caplog.text
    # The load runs beside the microphone now, so the failure line lands a
    # moment after the turn it did not hold up (ADR-0115).
    assert await _wait_until(lambda: "❗ emotion model failed to load" in caplog.text)


class WordsBackend(AnyDictationBackend):
    async def transcribe(self, audio: bytes) -> str:
        return audio.decode()


class FakeDetector:
    def __init__(self, model, min_score, out_of_process=False):
        self.prepared = 0

    async def prepare(self, report):
        self.prepared += 1

    async def hear(self, audio):
        return Tone("sad", 0.82) if b"sorry" in audio else None

    def close(self):
        pass


def _session_hearing(monkeypatch, *said: str, detect_emotion: bool):
    async def listen(config, should_listen, **kwargs):
        for i, text in enumerate(said):
            yield Utterance(text.encode(), i, i + 1)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))
    monkeypatch.setattr("zrb.llm.dictation.feature.EmotionDetector", FakeDetector)
    config = DictationConfig(
        backend=WordsBackend(), mode="hands_free", detect_emotion=detect_emotion
    )
    return DictationSession(config.resolve())


async def _sources(session: DictationSession, count: int):
    stream = session.listen_hands_free()
    replies = [await anext(stream) for _ in range(count)]
    await stream.aclose()
    return [(reply.text, reply.source) for reply in replies]


@pytest.mark.asyncio
async def test_the_tone_rides_on_the_turn_and_the_words_stay_clean(monkeypatch):
    session = _session_hearing(
        monkeypatch, "I am so sorry", "open the file", detect_emotion=True
    )

    sad, plain = await _sources(session, 2)

    assert sad[0] == "I am so sorry"
    assert (sad[1].tone, sad[1].tone_score) == ("sad", 0.82)
    assert "sounding sad (0.82)" in sad[1].render()
    assert plain == ("open the file", DICTATION_INPUT)


@pytest.mark.asyncio
async def test_no_tone_is_heard_unless_detection_is_on(monkeypatch):
    session = _session_hearing(monkeypatch, "I am so sorry", detect_emotion=False)

    assert await _sources(session, 1) == [("I am so sorry", DICTATION_INPUT)]


@pytest.mark.asyncio
async def test_the_microphone_listens_before_the_emotion_model_loads(monkeypatch):
    """A tone is worth a wait; a microphone is not. The transcriber is loaded
    before listening starts, and the emotion model beside it (ADR-0115)."""
    started = asyncio.Event()
    finish = asyncio.Event()

    class SlowDetector(FakeDetector):
        async def prepare(self, report):
            started.set()
            await finish.wait()

    _session_hearing(monkeypatch, "hello", detect_emotion=True)
    monkeypatch.setattr("zrb.llm.dictation.feature.EmotionDetector", SlowDetector)
    session = DictationSession(
        DictationConfig(
            backend=WordsBackend(), mode="hands_free", detect_emotion=True
        ).resolve()
    )

    replies = await asyncio.wait_for(_sources(session, 1), timeout=2)
    try:
        assert replies == [("hello", DICTATION_INPUT)]
        assert started.is_set()  # the load began
        assert not finish.is_set()  # and the turn did not wait for it
    finally:
        finish.set()
        session.close()


@pytest.mark.asyncio
async def test_the_transcriber_is_still_loaded_before_listening(monkeypatch):
    """The words need the transcriber, so that one still comes first."""
    prepared: list[str] = []

    class SlowBackend(WordsBackend):
        async def prepare(self, report):
            prepared.append("transcriber")

    _session_hearing(monkeypatch, "hello", detect_emotion=False)
    session = DictationSession(
        DictationConfig(backend=SlowBackend(), mode="hands_free").resolve()
    )

    assert await _sources(session, 1) == [("hello", DICTATION_INPUT)]
    assert prepared == ["transcriber"]


@pytest.mark.asyncio
async def test_an_utterance_heard_while_the_model_loads_gets_no_tone(monkeypatch):
    """The load takes up to twenty seconds; a clip heard meanwhile is answered
    at once without a tone, not after waiting for the model."""
    loading = threading.Event()
    release = threading.Event()

    class SlowAutoModel:
        def __init__(self, model, disable_update):
            loading.set()
            release.wait(5)

        def generate(self, input, granularity, extract_embedding):
            return [{"labels": LABELS, "scores": [0.0, 0.9, 0.1, 0.0, 0.0]}]

    monkeypatch.setitem(
        sys.modules, "funasr", SimpleNamespace(AutoModel=SlowAutoModel)
    )
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(snapshot_download=lambda repo, local_files_only=True: repo),
    )
    detector = EmotionDetector("me/e2v")

    prepare = asyncio.create_task(detector.prepare(lambda message: None))
    assert await asyncio.to_thread(loading.wait, 5)
    assert await asyncio.wait_for(detector.hear(b"\x00\x10" * 160), timeout=2) is None

    release.set()
    await prepare
    assert await detector.hear(b"\x00\x10" * 160) == Tone("happy", 0.9)


@pytest.mark.asyncio
async def test_out_of_process_classifies_through_a_worker(monkeypatch):
    workers: list[FakeWorker] = []

    class FakeWorker:
        def __init__(self, repo):
            self.repo = repo
            self.closed = False
            self.is_started = False
            workers.append(self)

        def start(self):
            self.is_started = True
            return lambda samples: {
                "labels": LABELS,
                "scores": [0.0, 0.9, 0.1, 0.0, 0.0],
            }

        def close(self):
            self.closed = True
            self.is_started = False

    monkeypatch.setattr("zrb.llm.dictation.emotion.EmotionWorker", FakeWorker)
    detector = EmotionDetector("me/e2v", out_of_process=True)

    assert await detector.hear(b"\x00\x10" * 160) == Tone("happy", 0.9)
    detector.close()

    [worker] = workers
    assert worker.repo == "me/e2v"
    assert worker.closed


@pytest.mark.asyncio
async def test_a_worker_whose_child_died_is_started_again(monkeypatch):
    """One dead child costs the tones it would have heard, not every tone after
    it: the next clip starts another, up to `MAX_DEATHS` (ADR-0115)."""
    workers: list[DyingWorker] = []

    class DyingWorker:
        def __init__(self, repo):
            self.closed = False
            self.is_started = False
            workers.append(self)

        def start(self):
            self.is_started = True
            return self._classify

        def _classify(self, samples):
            if len(workers) == 1:
                # The kernel picked this child, as `make_expendable` asked it to.
                self.is_started = False
                raise RuntimeError("the emotion worker stopped (killed)")
            return {"labels": LABELS, "scores": [0.0, 0.9, 0.1, 0.0, 0.0]}

        def close(self):
            self.closed = True
            self.is_started = False

    monkeypatch.setattr("zrb.llm.dictation.emotion.EmotionWorker", DyingWorker)
    detector = EmotionDetector("me/e2v", out_of_process=True)
    clip = b"\x00\x10" * 160

    assert await detector.hear(clip) is None
    assert await detector.hear(clip) == Tone("happy", 0.9)

    assert len(workers) == 2
    detector.close()


@pytest.mark.asyncio
async def test_a_session_ending_mid_load_closes_the_worker_it_made(monkeypatch):
    """The model loads on a thread of its own, so a session can end before it
    lands. The child it made is then closed instead of kept: nothing can reach
    it, and it would hold its share of the machine for the rest of the chat."""
    started = threading.Event()
    release = threading.Event()
    workers: list[LoadingWorker] = []

    class LoadingWorker:
        def __init__(self, repo):
            self.closed = False
            self.is_started = False
            workers.append(self)

        def start(self):
            started.set()
            release.wait(5)
            self.is_started = True
            return lambda samples: {
                "labels": LABELS,
                "scores": [0.0, 0.9, 0.1, 0.0, 0.0],
            }

        def close(self):
            self.closed = True
            self.is_started = False

    monkeypatch.setattr(
        "zrb.llm.dictation.emotion.EmotionWorker", LoadingWorker
    )
    detector = EmotionDetector("me/e2v", out_of_process=True)
    prepare = asyncio.create_task(detector.prepare(lambda message: None))
    assert await asyncio.to_thread(started.wait, 5)

    prepare.cancel()  # what `_close_emotion` does to a load still running
    detector.close()
    # The worker was kept before its model loaded, so closing reaches it now
    # rather than when the load lands.
    assert workers[0].closed
    release.set()

    assert await _wait_until(lambda: bool(workers) and workers[0].closed)
    assert await detector.hear(b"\x00\x10" * 160) is None
    assert len(workers) == 1


@pytest.mark.asyncio
async def test_a_worker_that_cannot_start_costs_only_the_tone(monkeypatch, caplog):
    class DeadWorker:
        def __init__(self, repo):
            self.closed = False

        def start(self):
            raise RuntimeError("this machine has no room for it")

        def close(self):
            self.closed = True

    monkeypatch.setattr("zrb.llm.dictation.emotion.EmotionWorker", DeadWorker)
    detector = EmotionDetector(out_of_process=True)

    assert await detector.hear(b"\x00\x00") is None
    assert "no room for it" in detector.unavailable_reason
    assert "this machine has no room for it" in caplog.text


async def _wait_until(condition, timeout: float = 2.0) -> bool:
    """Wait for a background task's effect, up to *timeout* seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        await asyncio.sleep(0.01)
    return condition()
