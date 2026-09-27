import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.dictation.backend.google import GoogleDictationBackend


def _fake_genai(response_text):
    client = MagicMock()
    client.models.generate_content = MagicMock(
        return_value=MagicMock(text=response_text)
    )
    fake_types = MagicMock()
    fake_genai = MagicMock()
    fake_genai.Client = MagicMock(return_value=client)
    fake_genai.types = fake_types
    fake_google = MagicMock()
    fake_google.genai = fake_genai
    modules = patch.dict(
        "sys.modules",
        {
            "google": fake_google,
            "google.genai": fake_genai,
            "google.genai.types": fake_types,
        },
    )
    return modules, fake_genai, client, fake_types


def test_name_is_google():
    assert GoogleDictationBackend().name == "google"


@pytest.mark.asyncio
async def test_transcribe_strips_text_and_sends_wav():
    modules, fake_genai, client, fake_types = _fake_genai("  google text  ")
    backend = GoogleDictationBackend("gemini-x")
    with modules, patch.dict(os.environ, {"GEMINI_API_KEY": "g-key"}):
        result = await backend.transcribe(b"\x00\x01")

    assert result == "google text"
    fake_genai.Client.assert_called_once_with(api_key="g-key")
    assert client.models.generate_content.call_args.kwargs["model"] == "gemini-x"
    part_kwargs = fake_types.Part.from_bytes.call_args.kwargs
    assert part_kwargs["mime_type"] == "audio/wav"
    assert part_kwargs["data"].startswith(b"RIFF")


@pytest.mark.asyncio
async def test_transcribe_empty_response_returns_empty_string():
    modules, _, _, _ = _fake_genai(None)
    backend = GoogleDictationBackend(api_key="explicit")
    with modules, patch.dict(os.environ, {}, clear=True):
        assert await backend.transcribe(b"\x00\x01") == ""


@pytest.mark.asyncio
async def test_google_api_key_fallback_and_client_reuse():
    modules, fake_genai, _, _ = _fake_genai("hi")
    backend = GoogleDictationBackend()
    with modules, patch.dict(os.environ, {"GOOGLE_API_KEY": "fallback"}, clear=True):
        await backend.transcribe(b"a")
        await backend.transcribe(b"b")

    fake_genai.Client.assert_called_once_with(api_key="fallback")


@pytest.mark.asyncio
async def test_missing_google_genai_package_raises_install_hint():
    backend = GoogleDictationBackend()
    with patch.dict(
        "sys.modules",
        {"google": None, "google.genai": None, "google.genai.types": MagicMock()},
    ):
        with pytest.raises(RuntimeError, match="google-genai is not installed"):
            await backend.transcribe(b"a")


@pytest.mark.asyncio
async def test_missing_api_key_raises_clear_error():
    modules, fake_genai, _, _ = _fake_genai("hi")
    backend = GoogleDictationBackend()
    with modules, patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY .* is not set"):
            await backend.transcribe(b"a")
    fake_genai.Client.assert_not_called()
