import os
import wave
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.dictation.backend.openai import OpenAIDictationBackend


def _fake_openai(text="openai text"):
    client = MagicMock()
    client.audio.transcriptions.create = AsyncMock(return_value=MagicMock(text=text))
    fake_openai = MagicMock()
    fake_openai.AsyncOpenAI = MagicMock(return_value=client)
    return fake_openai, client


def test_name_is_openai():
    assert OpenAIDictationBackend().name == "openai"


@pytest.mark.asyncio
async def test_transcribe_sends_wav_to_the_transcription_api():
    fake_openai, client = _fake_openai()
    backend = OpenAIDictationBackend(
        "gpt-4o-transcribe", base_url="http://proxy", language="en"
    )
    with (
        patch.dict("sys.modules", {"openai": fake_openai}),
        patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake"}),
    ):
        result = await backend.transcribe(b"\x00\x01")

    assert result == "openai text"
    fake_openai.AsyncOpenAI.assert_called_once_with(
        api_key="sk-fake", base_url="http://proxy"
    )
    kwargs = client.audio.transcriptions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-transcribe"
    assert kwargs["language"] == "en"
    assert kwargs["file"].name == "audio.wav"
    with wave.open(BytesIO(kwargs["file"].getvalue()), "rb") as wav:
        assert wav.readframes(wav.getnframes()) == b"\x00\x01"


@pytest.mark.asyncio
async def test_explicit_api_key_wins_and_client_is_reused():
    fake_openai, _ = _fake_openai()
    backend = OpenAIDictationBackend(api_key="sk-explicit")
    with (
        patch.dict("sys.modules", {"openai": fake_openai}),
        patch.dict(os.environ, {}, clear=True),
    ):
        await backend.transcribe(b"a")
        await backend.transcribe(b"b")

    fake_openai.AsyncOpenAI.assert_called_once_with(
        api_key="sk-explicit", base_url=None
    )


@pytest.mark.asyncio
async def test_missing_openai_package_raises_install_hint():
    backend = OpenAIDictationBackend()
    with patch.dict("sys.modules", {"openai": None}):
        with pytest.raises(RuntimeError, match="openai is not installed"):
            await backend.transcribe(b"a")


@pytest.mark.asyncio
async def test_missing_api_key_raises_clear_error():
    fake_openai, _ = _fake_openai()
    backend = OpenAIDictationBackend()
    with (
        patch.dict("sys.modules", {"openai": fake_openai}),
        patch.dict(os.environ, {}, clear=True),
    ):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
            await backend.transcribe(b"a")
    fake_openai.AsyncOpenAI.assert_not_called()


def _segment(text, no_speech_prob=0.0, avg_logprob=-0.2, compression_ratio=1.4):
    return MagicMock(
        text=text,
        no_speech_prob=no_speech_prob,
        avg_logprob=avg_logprob,
        compression_ratio=compression_ratio,
    )


@pytest.mark.asyncio
async def test_a_whisper_model_leaves_out_segments_that_are_not_speech():
    """Whisper writes words for noise; its own scores say which: likely no
    speech it is unsure of, or text repeating itself."""
    fake_openai, client = _fake_openai()
    client.audio.transcriptions.create.return_value = MagicMock(
        text="and this and this run the tests",
        segments=[
            _segment(" and this", no_speech_prob=0.9, avg_logprob=-1.5),
            _segment(" and this and this", compression_ratio=3.1),
            _segment(" run the tests"),
            # Sure it is speech, though it sounds like silence: kept.
            _segment(" now", no_speech_prob=0.9, avg_logprob=-0.3),
        ],
    )
    with (
        patch.dict("sys.modules", {"openai": fake_openai}),
        patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake"}),
    ):
        result = await OpenAIDictationBackend(language="id").transcribe_speech(
            b"\x00\x01"
        )

    assert result == "run the tests now"
    kwargs = client.audio.transcriptions.create.call_args.kwargs
    assert kwargs["language"] == "id"
    assert kwargs["response_format"] == "verbose_json"


@pytest.mark.asyncio
async def test_a_model_without_segment_scores_is_taken_as_written():
    fake_openai, client = _fake_openai("hello there")
    with (
        patch.dict("sys.modules", {"openai": fake_openai}),
        patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake"}),
    ):
        backend = OpenAIDictationBackend("gpt-4o-transcribe")
        result = await backend.transcribe_speech(b"\x00")

    assert result == "hello there"
    assert "response_format" not in client.audio.transcriptions.create.call_args.kwargs


@pytest.mark.asyncio
async def test_transcribe_keeps_every_word_a_whisper_model_wrote():
    """Push-to-talk transcribes with `transcribe`: "test test test test" is
    repetitive, but the user chose to say it."""
    fake_openai, client = _fake_openai("test test test test")
    with (
        patch.dict("sys.modules", {"openai": fake_openai}),
        patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake"}),
    ):
        result = await OpenAIDictationBackend("whisper-1").transcribe(b"\x00")

    assert result == "test test test test"
    assert "response_format" not in client.audio.transcriptions.create.call_args.kwargs
    assert "response_format" not in client.audio.transcriptions.create.call_args.kwargs
