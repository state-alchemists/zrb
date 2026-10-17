import sys
from types import SimpleNamespace

import pytest

from zrb.llm.dictation.backend.sensevoice import SenseVoiceDictationBackend


class FakeRecognizer:
    def __init__(self, text, emotion):
        self.text, self.emotion = text, emotion
        self.heard: list = []

    def create_stream(self):
        heard = self.heard
        stream = SimpleNamespace(
            result=SimpleNamespace(text=self.text, emotion=self.emotion)
        )
        stream.accept_waveform = lambda rate, samples: heard.append(
            (rate, len(samples))
        )
        return stream

    def decode_stream(self, stream):
        pass


@pytest.fixture
def engine(monkeypatch):
    """A fake sherpa-onnx and Hugging Face download, recording what was built."""
    built: dict = {}
    recognizer = FakeRecognizer(" ship it ", "<|HAPPY|>")

    def from_sense_voice(**kwargs):
        built.update(kwargs)
        return recognizer

    asked: list = []

    def download(repo, name, local_files_only=False):
        asked.append((name, local_files_only))
        if local_files_only and not built.get("cached", True):
            raise FileNotFoundError(name)
        return f"/cache/{repo}/{name}"

    offline = SimpleNamespace(from_sense_voice=from_sense_voice)
    monkeypatch.setitem(
        sys.modules, "sherpa_onnx", SimpleNamespace(OfflineRecognizer=offline)
    )
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(hf_hub_download=download),
    )
    return SimpleNamespace(built=built, recognizer=recognizer, asked=asked)


@pytest.mark.asyncio
async def test_the_words_come_back_trimmed_and_its_emotion_tag_unread(engine):
    pcm = b"\x00\x10" * 1600

    assert await SenseVoiceDictationBackend("r").transcribe(pcm) == "ship it"
    assert engine.recognizer.heard[-1] == (16000, 1600)


@pytest.mark.asyncio
async def test_the_model_comes_from_the_repo_and_loads_once(engine):
    backend = SenseVoiceDictationBackend("me/sv", language="en", num_threads=2)

    await backend.transcribe(b"\x00\x00" * 160)
    engine.built.clear()
    await backend.transcribe(b"\x00\x00" * 160)

    assert engine.built == {}
    assert backend.name == "sensevoice"


@pytest.mark.asyncio
async def test_the_model_files_and_settings_reach_the_engine(engine):
    await SenseVoiceDictationBackend("me/sv", num_threads=2).transcribe(b"\x00\x00")

    assert engine.built["model"] == "/cache/me/sv/model.int8.onnx"
    assert engine.built["tokens"] == "/cache/me/sv/tokens.txt"
    assert engine.built["num_threads"] == 2
    assert engine.built["language"] == "auto"


@pytest.mark.asyncio
async def test_a_missing_engine_names_what_to_install(monkeypatch):
    monkeypatch.setitem(sys.modules, "sherpa_onnx", None)

    with pytest.raises(RuntimeError, match="pip install sherpa-onnx"):
        await SenseVoiceDictationBackend("r").transcribe(b"\x00\x00")


@pytest.mark.asyncio
async def test_prepare_loads_the_model_before_the_first_recording(engine):
    backend = SenseVoiceDictationBackend("me/sv")
    reports: list[str] = []

    await backend.prepare(reports.append)
    await backend.prepare(reports.append)

    assert engine.built["model"] == "/cache/me/sv/model.int8.onnx"
    assert reports == ["Loading the sensevoice model…"]


@pytest.mark.asyncio
async def test_no_model_or_thread_count_takes_the_defaults(engine):
    await SenseVoiceDictationBackend(None, num_threads=None).prepare(
        lambda message: None
    )

    assert engine.built["model"].endswith(
        "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.int8.onnx"
    )
    assert engine.built["num_threads"] == 4


@pytest.mark.asyncio
async def test_a_cached_model_is_used_without_asking_the_hub(engine):
    await SenseVoiceDictationBackend("me/sv").prepare(lambda message: None)

    assert engine.asked == [("model.int8.onnx", True), ("tokens.txt", True)]


@pytest.mark.asyncio
async def test_a_model_not_cached_yet_is_downloaded(engine):
    engine.built["cached"] = False

    await SenseVoiceDictationBackend("me/sv").prepare(lambda message: None)

    assert ("model.int8.onnx", False) in engine.asked
