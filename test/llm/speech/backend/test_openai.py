"""`OpenAISpeechBackend`."""

import io
import json
import os
import struct

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


@pytest.mark.parametrize(
    "model, style, instructions",
    [
        ("gpt-4o-mini-tts", "Warm and clear.", "Warm and clear."),
        ("gpt-4o-mini-tts", "", None),
        ("tts-1-hd", "Warm and clear.", None),
    ],
)
def test_openai_sends_the_style_as_instructions_to_a_model_that_takes_them(
    requests, which, monkeypatch, model, style, instructions
):
    sent, replies = requests
    replies.append(b"RIFF-wav")
    which("afplay")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    OpenAISpeechBackend(model=model, style=style).create_utterance("hi").cleanup()

    body = json.loads(sent[0][0].data)
    assert body.get("instructions") == instructions


def _streamed_wav(pcm: bytes, rate: int = 24000) -> bytes:
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    header = b"RIFF\xff\xff\xff\xffWAVEfmt " + struct.pack("<I", 16) + fmt
    return header + b"data\xff\xff\xff\xff" + pcm


def test_openai_renders_the_streamed_wav_as_audio(requests, monkeypatch):
    sent, replies = requests
    replies.append(_streamed_wav(b"\x01\x00" * 3))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    audio = OpenAISpeechBackend().create_audio("hi")

    assert audio.sample_rate == 24000
    assert b"".join(audio.chunks) == b"\x01\x00" * 3
    audio.close()
    assert json.loads(sent[0][0].data)["response_format"] == "wav"


def test_openai_closes_a_response_that_is_not_audio(requests, monkeypatch):
    sent, replies = requests
    replies.append(b"not a wav at all")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with pytest.raises(RuntimeError, match="not a WAV"):
        OpenAISpeechBackend().create_audio("hi")
