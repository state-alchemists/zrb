"""`GeminiSpeechBackend`."""

import base64
import io
import json
import wave

import pytest

from zrb.llm.speech.backend import GeminiSpeechBackend


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


def test_gemini_wraps_the_pcm_it_returns_in_a_wav(requests, monkeypatch):
    sent, replies = requests
    pcm = b"\x00\x01" * 10
    part = {"inlineData": {"data": base64.b64encode(pcm).decode()}}
    replies.append(
        json.dumps({"candidates": [{"content": {"parts": [part]}}]}).encode()
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key")

    utterance = GeminiSpeechBackend(
        voice="Kore", wav_player="mpv --quiet"
    ).create_utterance("hello")

    request, _ = sent[0]
    assert request.get_header("X-goog-api-key") == "g-key"
    body = json.loads(request.data)
    assert body["contents"][0]["parts"][0]["text"] == "Say: hello"
    assert utterance.argv[:2] == ["mpv", "--quiet"]
    with wave.open(utterance.argv[-1], "rb") as wav:
        assert wav.getframerate() == 24000
        assert wav.readframes(10) == pcm
    utterance.cleanup()


def test_gemini_joins_audio_split_across_parts(requests, monkeypatch):
    sent, replies = requests
    first, second = b"\x00\x01" * 5, b"\x02\x03" * 5
    parts = [
        {"inlineData": {"data": base64.b64encode(first).decode()}},
        {"text": "not audio"},
        {"inlineData": {"data": base64.b64encode(second).decode()}},
    ]
    replies.append(json.dumps({"candidates": [{"content": {"parts": parts}}]}).encode())
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    utterance = GeminiSpeechBackend(wav_player="mpv").create_utterance("hello")

    with wave.open(utterance.argv[-1], "rb") as wav:
        assert wav.readframes(20) == first + second
    utterance.cleanup()


def test_gemini_without_audio_raises_so_zrb_falls_back(requests, monkeypatch):
    _, replies = requests
    parts = [{"text": "I can't say that."}]
    replies.append(json.dumps({"candidates": [{"content": {"parts": parts}}]}).encode())
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    with pytest.raises(RuntimeError, match="no audio"):
        GeminiSpeechBackend().create_utterance("hello")


def test_gemini_without_a_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        GeminiSpeechBackend().create_utterance("hello")


def test_gemini_puts_the_style_ahead_of_the_text_to_read(requests, monkeypatch):
    sent, replies = requests
    part = {"inlineData": {"data": base64.b64encode(b"\x00\x01").decode()}}
    replies.append(
        json.dumps({"candidates": [{"content": {"parts": [part]}}]}).encode()
    )
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")

    # create_audio: the prompt is the point, and it needs no WAV player.
    GeminiSpeechBackend(style="Warm and clear.").create_audio("hello")

    text = json.loads(sent[0][0].data)["contents"][0]["parts"][0]["text"]
    assert text == "Warm and clear.\n\nSay exactly this, and nothing else: hello"


def test_gemini_renders_its_pcm_as_24_khz_audio(requests, monkeypatch):
    sent, replies = requests
    part = {"inlineData": {"data": base64.b64encode(b"\x03\x00").decode()}}
    replies.append(
        json.dumps({"candidates": [{"content": {"parts": [part]}}]}).encode()
    )
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")

    audio = GeminiSpeechBackend().create_audio("hi")

    assert audio.sample_rate == 24000
    assert list(audio.chunks) == [b"\x03\x00"]


@pytest.mark.parametrize(
    "style, expected",
    [("", "Bacakan: hello"), ("Ceria.", "Ceria. | hello")],
)
def test_gemini_prompts_are_configured(requests, monkeypatch, style, expected):
    sent, replies = requests
    part = {"inlineData": {"data": base64.b64encode(b"\x00\x01").decode()}}
    replies.append(
        json.dumps({"candidates": [{"content": {"parts": [part]}}]}).encode()
    )
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    backend = GeminiSpeechBackend(
        style=style, prompt="Bacakan: {text}", style_prompt="{style} | {text}"
    )

    backend.create_audio("hello")

    text = json.loads(sent[0][0].data)["contents"][0]["parts"][0]["text"]
    assert text == expected
