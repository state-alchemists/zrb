"""Tests for the voice engine module.

All audio I/O is mocked — no real microphone or STT backend is required.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.voice.engine import VoiceEngine, download_vosk_model


def asyncio_run(coro):
    """Helper to run a coroutine synchronously in tests."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


class TestOpenAITranscriber:
    """Tests for the OpenAI Whisper backend factory."""

    def test_transcribe(self):
        engine = VoiceEngine()
        result_obj = MagicMock()
        result_obj.text = "openai text"
        client = MagicMock()
        client.audio.transcriptions.create = AsyncMock(return_value=result_obj)
        fake_openai = MagicMock()
        fake_openai.AsyncOpenAI = MagicMock(return_value=client)
        with (
            patch.dict("sys.modules", {"openai": fake_openai}),
            patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake"}),
        ):
            transcribe = engine.make_openai_transcriber()
            assert asyncio_run(transcribe(b"\x00\x01")) == "openai text"

    def test_import_error(self):
        engine = VoiceEngine()
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError, match="openai is not installed"):
                engine.make_openai_transcriber()

    def test_missing_api_key_raises(self):
        """No OPENAI_API_KEY set -> a clear RuntimeError, not an opaque SDK error."""
        engine = VoiceEngine()
        fake_openai = MagicMock()
        with (
            patch.dict("sys.modules", {"openai": fake_openai}),
            patch.dict(os.environ, {}, clear=True),
        ):
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
                engine.make_openai_transcriber()


class TestGoogleTranscriber:
    """Tests for the Google Gemini STT backend factory."""

    def _patch_genai(self, response):
        client = MagicMock()
        client.models.generate_content = MagicMock(return_value=response)
        fake_genai = MagicMock()
        fake_genai.Client = MagicMock(return_value=client)
        fake_google = MagicMock()
        fake_google.genai = fake_genai
        return patch.dict(
            "sys.modules",
            {
                "google": fake_google,
                "google.genai": fake_genai,
                "google.genai.types": MagicMock(),
            },
        )

    def test_transcribe_strips_text(self):
        engine = VoiceEngine()
        response = MagicMock()
        response.text = "  google text  "
        with (
            self._patch_genai(response),
            patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}),
        ):
            transcribe = engine.make_google_transcriber()
            assert asyncio_run(transcribe(b"\x00\x01")) == "google text"

    def test_transcribe_empty_text(self):
        engine = VoiceEngine()
        response = MagicMock()
        response.text = None
        with (
            self._patch_genai(response),
            patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}),
        ):
            transcribe = engine.make_google_transcriber()
            assert asyncio_run(transcribe(b"\x00\x01")) == ""

    def test_import_error(self):
        engine = VoiceEngine()
        with patch.dict("sys.modules", {"google": None}):
            with pytest.raises(ImportError, match="google-genai is not installed"):
                engine.make_google_transcriber()

    def test_missing_api_key_raises(self):
        """Neither GEMINI_API_KEY nor GOOGLE_API_KEY set -> a clear RuntimeError."""
        engine = VoiceEngine()
        with (
            self._patch_genai(MagicMock()),
            patch.dict(os.environ, {}, clear=True),
        ):
            with pytest.raises(RuntimeError, match="GEMINI_API_KEY .* is not set"):
                engine.make_google_transcriber()


class TestGetTranscriberDispatch:
    """The mode dispatch in _get_transcriber resolves the right factory."""

    def test_dispatches_openai(self):
        engine = VoiceEngine()
        sentinel = AsyncMock()
        with (
            patch.object(engine, "make_openai_transcriber", return_value=sentinel),
            patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "openai"}),
        ):
            assert asyncio_run(engine.get_transcriber()) is sentinel

    def test_dispatches_google(self):
        engine = VoiceEngine()
        sentinel = AsyncMock()
        with (
            patch.object(engine, "make_google_transcriber", return_value=sentinel),
            patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "google"}),
        ):
            assert asyncio_run(engine.get_transcriber()) is sentinel


class TestMultimodalCapabilityGate:
    """The multimodal backend rejects models that can't accept audio."""

    def test_unsupported_modality_rejected(self):
        engine = VoiceEngine()
        engine.transcriber = None
        with (
            patch(
                "zrb.llm.agent_state.get_current_multimodal_model",
                return_value="gemini:gemini-2.5-flash",
            ),
            patch(
                "zrb.llm.config.model_resolver.resolve_configured_multimodal_model",
                return_value="gemini:gemini-2.5-flash",
            ),
            patch("zrb.llm.util.capabilities.model_capabilities") as mock_caps,
            patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "multimodal"}),
        ):
            mock_caps.supports_modality.return_value = False
            with pytest.raises(RuntimeError, match="does not support audio"):
                asyncio_run(engine.get_transcriber())


class TestEngineHelpers:
    """Tests for module-level helper functions."""

    def test_is_openai_chat_model_strings(self):
        from zrb.llm.voice.engine import is_openai_chat_model

        assert is_openai_chat_model("openai:gpt-4o") is True
        assert is_openai_chat_model("gpt-4o") is True
        assert is_openai_chat_model("o1-mini") is True
        assert is_openai_chat_model("gemini-2.5-flash") is False
        assert is_openai_chat_model(123) is False

    def test_is_openai_chat_model_instance(self):
        from zrb.llm.voice.engine import is_openai_chat_model

        class FakeModel:
            pass

        fake_mod = MagicMock()
        fake_mod.OpenAIChatModel = FakeModel
        with patch.dict("sys.modules", {"pydantic_ai.models.openai": fake_mod}):
            assert is_openai_chat_model(FakeModel()) is True

    def test_is_openai_chat_model_import_fallback(self):
        from zrb.llm.voice.engine import is_openai_chat_model

        with patch.dict("sys.modules", {"pydantic_ai.models.openai": None}):
            assert is_openai_chat_model("openai:foo") is True
            assert is_openai_chat_model("bar") is False

    def test_model_name_variants(self):
        from zrb.llm.voice.engine import model_name

        assert model_name("gpt-4o") == "gpt-4o"

        obj = MagicMock()
        obj.model_name = "the-model"
        assert model_name(obj) == "the-model"

        class NoName:
            model_name = None
            name = None

        assert model_name(NoName()) == "NoName"

    def test_get_vosk_model_dir_cache_hit(self):
        from zrb.llm.voice.engine import get_vosk_model_dir

        with patch("os.path.isdir", side_effect=lambda p: p.endswith("mymodel")):
            assert get_vosk_model_dir("mymodel").endswith("mymodel")

    def test_get_vosk_model_dir_env_hit(self):
        from zrb.llm.voice.engine import get_vosk_model_dir

        with (
            patch("os.path.isdir", side_effect=lambda p: p == "/env/model"),
            patch.dict(os.environ, {"VOSK_MODEL_PATH": "/env/model"}),
        ):
            assert get_vosk_model_dir("missing") == "/env/model"

    def test_get_vosk_model_dir_none(self):
        from zrb.llm.voice.engine import get_vosk_model_dir

        with (
            patch("os.path.isdir", return_value=False),
            patch.dict(os.environ, {}, clear=True),
        ):
            assert get_vosk_model_dir("missing") is None

    def test_pcm16_to_wav_bytes_produces_valid_wav(self):
        import wave
        from io import BytesIO

        from zrb.llm.voice.engine import pcm16_to_wav_bytes

        pcm = (b"\x01\x00\x02\x00") * 4  # 4 fake int16 samples
        wav_bytes = pcm16_to_wav_bytes(pcm)

        assert wav_bytes.startswith(b"RIFF")
        with wave.open(BytesIO(wav_bytes), "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == 16000
            assert wav.readframes(wav.getnframes()) == pcm


class TestDownloadVoskModelBranches:
    """Additional branches of the chunked download helper."""

    def test_read_failure_raises(self):
        fake_resp = MagicMock()
        fake_resp.read.side_effect = OSError("read broke")
        with (
            patch("urllib.request.urlopen", return_value=fake_resp),
            patch("os.makedirs"),
        ):
            with pytest.raises(RuntimeError, match="Failed to download Vosk model"):
                asyncio_run(download_vosk_model("m", "http://host"))
        fake_resp.close.assert_called_once()

    def test_missing_dir_after_extract_raises(self):
        fake_resp = MagicMock()
        fake_resp.read.side_effect = [b"data", b""]
        with (
            patch("urllib.request.urlopen", return_value=fake_resp),
            patch("zipfile.ZipFile"),
            patch("os.makedirs"),
            patch("os.path.isdir", return_value=False),
        ):
            with pytest.raises(
                RuntimeError, match="did not produce expected directory"
            ):
                asyncio_run(download_vosk_model("m", "http://host"))

    def test_rejects_zip_slip_member_path(self):
        """A zip member escaping the cache dir (zip-slip) is refused, not extracted."""
        fake_resp = MagicMock()
        fake_resp.read.side_effect = [b"data", b""]
        fake_zip = MagicMock()
        fake_zip.__enter__.return_value = fake_zip
        fake_zip.namelist.return_value = ["../../etc/passwd"]
        with (
            patch("urllib.request.urlopen", return_value=fake_resp),
            patch("zipfile.ZipFile", return_value=fake_zip),
            patch("os.makedirs"),
        ):
            with pytest.raises(RuntimeError, match="unsafe path in archive member"):
                asyncio_run(download_vosk_model("m", "http://host"))
        fake_zip.extractall.assert_not_called()

    def test_accepts_safe_zip_members(self):
        """Ordinary in-tree members extract normally (no false positive)."""
        fake_resp = MagicMock()
        fake_resp.read.side_effect = [b"data", b""]
        fake_zip = MagicMock()
        fake_zip.__enter__.return_value = fake_zip
        fake_zip.namelist.return_value = ["model-x/conf.json", "model-x/am/final.mdl"]
        with (
            patch("urllib.request.urlopen", return_value=fake_resp),
            patch("zipfile.ZipFile", return_value=fake_zip),
            patch("os.makedirs"),
            patch("os.path.isdir", return_value=True),
        ):
            asyncio_run(download_vosk_model("model-x", "http://host"))
        fake_zip.extractall.assert_called_once()
