"""The speaker's tone: emotion2vec+ beside the transcriber, carried by the turn."""

import asyncio
import sys
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
    assert "❗ emotion model failed to load" in caplog.text


class WordsBackend(AnyDictationBackend):
    async def transcribe(self, audio: bytes) -> str:
        return audio.decode()


class FakeDetector:
    def __init__(self, model, min_score):
        self.prepared = 0

    async def prepare(self, report):
        self.prepared += 1

    async def hear(self, audio):
        return Tone("sad", 0.82) if b"sorry" in audio else None


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
async def test_the_transcriber_and_the_emotion_model_load_at_the_same_time(
    monkeypatch,
):
    both_loading = asyncio.Event()
    started: list[str] = []

    async def load(name: str) -> None:
        started.append(name)
        if len(started) == 2:
            both_loading.set()
        # Neither load finishes until the other has started.
        await asyncio.wait_for(both_loading.wait(), timeout=2)

    class SlowBackend(WordsBackend):
        async def prepare(self, report):
            await load("transcriber")

    class SlowDetector(FakeDetector):
        async def prepare(self, report):
            await load("emotion")

    _session_hearing(monkeypatch, "hello", detect_emotion=True)
    monkeypatch.setattr("zrb.llm.dictation.feature.EmotionDetector", SlowDetector)
    session = DictationSession(
        DictationConfig(
            backend=SlowBackend(), mode="hands_free", detect_emotion=True
        ).resolve()
    )

    assert await _sources(session, 1) == [("hello", DICTATION_INPUT)]
    assert sorted(started) == ["emotion", "transcriber"]
