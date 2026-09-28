"""`OpenAISpeechBackend`."""

import io
import json
import os

import pytest

from zrb.llm.speech.backend import OpenAISpeechBackend
from zrb.llm.speech.backend.utterance import StreamedUtterance


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def requests(monkeypatch):
    """Record each urlopen request and answer with the queued bodies."""
    sent: list = []
    replies: list[bytes] = []

    def urlopen(request, timeout=None):
        sent.append((request, timeout))
        return _Response(replies.pop(0))

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return sent, replies


@pytest.fixture
def which(monkeypatch):
    def only(*names):
        monkeypatch.setattr(
            "shutil.which", lambda name: f"/usr/bin/{name}" if name in names else None
        )

    return only


def test_openai_posts_the_text_and_plays_the_wav(requests, which, monkeypatch):
    sent, replies = requests
    replies.append(b"RIFF-wav")
    which("afplay")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    backend = OpenAISpeechBackend(
        voice="nova", model="tts-1", base_url="https://api.example/v1/", timeout=3
    )

    utterance = backend.create_utterance("hello")

    request, timeout = sent[0]
    assert request.full_url == "https://api.example/v1/audio/speech"
    assert json.loads(request.data) == {
        "model": "tts-1",
        "voice": "nova",
        "input": "hello",
        "response_format": "wav",
    }
    assert request.get_header("Authorization") == "Bearer sk-test"
    assert timeout == 3
    assert utterance.argv[0] == "afplay"
    with open(utterance.argv[-1], "rb") as wav_file:
        assert wav_file.read() == b"RIFF-wav"
    utterance.cleanup()
    assert not os.path.exists(utterance.argv[-1])
    assert backend.name == "openai"


def test_openai_streams_into_a_player_that_reads_stdin(requests, which, monkeypatch):
    sent, replies = requests
    replies.append(b"RIFF-wav")
    which("paplay")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    utterance = OpenAISpeechBackend().create_utterance("hello")

    assert isinstance(utterance, StreamedUtterance)
    assert utterance.argv == ["paplay"]


def test_openai_without_a_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAISpeechBackend().create_utterance("hello")


def test_openai_without_a_timeout_still_bounds_a_stalled_download(
    requests, which, monkeypatch
):
    sent, replies = requests
    replies.append(b"RIFF-wav")
    which("afplay")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    OpenAISpeechBackend().create_utterance("hello").cleanup()

    _, timeout = sent[0]
    assert timeout is not None
