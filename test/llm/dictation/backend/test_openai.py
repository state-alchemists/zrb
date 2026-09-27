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
    backend = OpenAIDictationBackend("gpt-4o-transcribe", base_url="http://proxy")
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
