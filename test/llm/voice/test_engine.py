"""Tests for the voice engine module.

All audio I/O is mocked — no real microphone or STT backend is required.
"""

import asyncio
import os
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.voice.engine import VoiceEngine, _download_vosk_model


class TestVoiceEngine:
    """Tests for VoiceEngine.start_listening()."""

    @pytest.fixture
    def engine(self):
        return VoiceEngine()

    @pytest.fixture
    def stop_event(self):
        return asyncio.Event()

    def test_start_listening_raises_on_import_error(self, engine, stop_event):
        """When sounddevice is not installed, raise ImportError."""
        with patch.object(engine, "_record", side_effect=ImportError("No sounddevice")):
            with pytest.raises(ImportError, match="No sounddevice"):
                asyncio_run(engine.start_listening(stop_event))

    def test_start_listening_raises_on_exception(self, engine, stop_event):
        """When recording raises, propagate the error."""
        with patch.object(engine, "_record", side_effect=RuntimeError("mic broken")):
            with pytest.raises(RuntimeError, match="mic broken"):
                asyncio_run(engine.start_listening(stop_event))

    def test_start_listening_returns_empty_for_no_audio(self, engine, stop_event):
        """When no audio is captured, return empty string."""
        with patch.object(engine, "_record", new_callable=AsyncMock, return_value=b""):
            result = asyncio_run(engine.start_listening(stop_event))
            assert result == ""

    def test_start_listening_transcribes_audio(self, engine, stop_event):
        """When audio is captured, transcribe and return text."""
        with patch.object(
            engine, "_record", new_callable=AsyncMock, return_value=b"fake_audio"
        ):
            with patch.object(
                engine, "_transcribe", new_callable=AsyncMock, return_value="hello"
            ):
                result = asyncio_run(engine.start_listening(stop_event))
                assert result == "hello"

    def test_transcribe_delegates_to_backend(self, engine):
        """_transcribe resolves the backend and calls it with the audio."""
        transcriber = AsyncMock(return_value="decoded")
        with patch.object(
            engine, "_get_transcriber", new_callable=AsyncMock, return_value=transcriber
        ):
            assert asyncio_run(engine._transcribe(b"audio")) == "decoded"
        transcriber.assert_awaited_once_with(b"audio")

    def test_get_transcriber_unknown_mode_raises(self, engine):
        """Unknown voice mode raises RuntimeError."""
        with patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "unknown"}):
            engine._transcriber = None
            with pytest.raises(RuntimeError, match="Unknown voice mode"):
                asyncio_run(engine._get_transcriber())

    def test_get_transcriber_vosk_unavailable_raises(self, engine):
        """When vosk is not installed, raises RuntimeError."""
        engine._transcriber = None
        with patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "vosk"}):
            with patch.object(
                engine,
                "_make_vosk_transcriber",
                side_effect=ImportError("No vosk"),
            ):
                with pytest.raises(RuntimeError, match="missing dependencies"):
                    asyncio_run(engine._get_transcriber())

    def test_get_transcriber_openai_unavailable_raises(self, engine):
        """When openai is not installed, raises RuntimeError."""
        engine._transcriber = None
        with patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "openai"}):
            with patch.object(
                engine,
                "_make_openai_transcriber",
                side_effect=ImportError("No openai"),
            ):
                with pytest.raises(RuntimeError, match="missing dependencies"):
                    asyncio_run(engine._get_transcriber())

    def test_get_transcriber_multimodal_requires_model(self, engine):
        """When multimodal model is None, multimodal mode raises."""
        engine._transcriber = None
        with (
            patch("zrb.llm.config.config.llm_config") as mock_cfg,
            patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "multimodal"}),
        ):
            mock_cfg.multimodal_model = None
            with pytest.raises(RuntimeError, match="LLM_MULTIMODAL_MODEL"):
                asyncio_run(engine._get_transcriber())

    def test_get_transcriber_multimodal_creates_agent(self, engine):
        """With a non-OpenAI multimodal model, transcribes via agent."""
        engine._transcriber = None
        with (
            patch("zrb.llm.config.config.llm_config") as mock_cfg,
            patch("zrb.llm.agent.create_agent") as mock_create,
            patch("zrb.llm.agent.run_agent", new_callable=AsyncMock) as mock_run,
            patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "multimodal"}),
        ):
            mock_cfg.multimodal_model = "gemini:gemini-2.5-flash"
            mock_cfg.resolve_model.return_value = "gemini:gemini-2.5-flash"
            mock_create.return_value = "mock-agent"
            mock_run.return_value = ("hello world", None)

            transcriber = asyncio_run(engine._get_transcriber())
            result = asyncio_run(transcriber(b"fake_audio"))

            assert result == "hello world"

    def test_get_transcriber_multimodal_openai_rejected(self, engine):
        """OpenAI models raise a helpful RuntimeError in multimodal mode."""
        engine._transcriber = None
        with (
            patch("zrb.llm.config.config.llm_config") as mock_cfg,
            patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "multimodal"}),
        ):
            mock_cfg.multimodal_model = "openai:gpt-4o"
            mock_cfg.resolve_model.return_value = "openai:gpt-4o"
            with pytest.raises(RuntimeError, match="does not accept audio"):
                asyncio_run(engine._get_transcriber())

    def test_get_transcriber_multimodal_unavailable_raises(self, engine):
        """When _make_multimodal_transcriber raises ImportError, re-raised as RuntimeError."""
        engine._transcriber = None
        with patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "multimodal"}):
            with patch.object(
                engine,
                "_make_multimodal_transcriber",
                side_effect=ImportError("No agent deps"),
            ):
                with pytest.raises(RuntimeError, match="missing dependencies"):
                    asyncio_run(engine._get_transcriber())

    def test_transcriber_caches_result(self, engine):
        """The transcriber is cached after first resolution."""
        engine._transcriber = None
        mock_transcriber = AsyncMock(return_value="cached")
        with patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "vosk"}):
            with patch.object(
                engine,
                "_make_vosk_transcriber",
                new_callable=AsyncMock,
                return_value=mock_transcriber,
            ):
                first = asyncio_run(engine._get_transcriber())
                second = asyncio_run(engine._get_transcriber())
                assert first is second
                assert first is mock_transcriber

    def test_record_checks_stop_event(self, engine):
        """Recording loop exits when stop_event is set."""
        stop_event = asyncio.Event()
        stop_event.set()

        with patch.object(
            engine, "_transcribe", new_callable=AsyncMock, return_value="result"
        ):
            result = asyncio_run(engine.start_listening(stop_event))
            # With stop_event pre-set, no audio is captured -> empty
            assert result == ""


class TestDownloadVoskModel:
    """Tests for the chunked, cancellable Vosk model download."""

    def test_reads_body_in_chunks_then_extracts(self):
        """The response body is read in chunks, joined, and extracted."""
        fake_resp = MagicMock()
        fake_resp.read.side_effect = [b"PK\x03\x04", b"payload", b""]
        with (
            patch("urllib.request.urlopen", return_value=fake_resp),
            patch("zipfile.ZipFile"),
            patch("os.makedirs"),
            patch("os.path.isdir", return_value=True),
        ):
            result = asyncio_run(_download_vosk_model("model-x", "http://host"))

        assert result.endswith(os.path.join("vosk", "model-x"))
        # Read was called until it returned b"" (EOF).
        assert fake_resp.read.call_count == 3
        fake_resp.close.assert_called_once()

    def test_open_failure_raises_runtime_error(self):
        """A failure opening the URL is wrapped with recovery guidance."""
        with (
            patch("urllib.request.urlopen", side_effect=OSError("connection refused")),
            patch("os.makedirs"),
        ):
            with pytest.raises(RuntimeError, match="Failed to download Vosk model"):
                asyncio_run(_download_vosk_model("model-x", "http://host"))

    def test_cancellation_aborts_and_closes_socket(self):
        """Cancelling mid-read aborts at the chunk boundary and closes the socket."""

        async def scenario():
            fake_resp = MagicMock()
            release = threading.Event()

            def blocking_read(_n):
                # Simulate a slow read that only returns once released.
                release.wait(timeout=5)
                return b""

            fake_resp.read.side_effect = blocking_read

            with (
                patch("urllib.request.urlopen", return_value=fake_resp),
                patch("os.makedirs"),
            ):
                task = asyncio.create_task(
                    _download_vosk_model("model-x", "http://host")
                )
                # Let the coroutine reach the awaited (blocking) read.
                await asyncio.sleep(0.1)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                # finally: closed the socket even though we never finished.
                fake_resp.close.assert_called_once()
                release.set()  # let the worker thread unwind

        asyncio.run(scenario())


class TestRecord:
    """Tests for VoiceEngine._record() with mocked sounddevice."""

    @staticmethod
    def _fake_stream_factory(captured):
        class FakeStream:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def make_stream(samplerate, channels, callback):
            captured["callback"] = callback
            return FakeStream()

        return make_stream

    def test_captures_audio_then_stops(self):
        """A captured block is concatenated and returned as int16 PCM bytes."""

        async def scenario():
            import numpy as np

            engine = VoiceEngine()
            stop_event = asyncio.Event()
            captured = {}
            fake_sd = MagicMock()
            fake_sd.InputStream.side_effect = self._fake_stream_factory(captured)

            with patch.dict("sys.modules", {"sounddevice": fake_sd}):
                task = asyncio.create_task(engine._record(stop_event))
                await asyncio.sleep(0)  # let _record reach InputStream
                cb = captured["callback"]
                # status-truthy branch, then a normal block.
                cb(np.array([[0.5]], dtype=np.float32), 1, None, "overflow")
                cb(np.array([[0.25]], dtype=np.float32), 1, None, None)
                await asyncio.sleep(0.15)  # let queue.get pull a block
                stop_event.set()
                result = await task

            assert isinstance(result, bytes)
            assert len(result) > 0

        asyncio.run(scenario())

    def test_no_audio_returns_empty_bytes(self):
        """A pre-set stop_event yields no blocks -> empty bytes."""

        async def scenario():
            engine = VoiceEngine()
            stop_event = asyncio.Event()
            stop_event.set()
            fake_sd = MagicMock()
            fake_sd.InputStream.side_effect = self._fake_stream_factory({})

            with patch.dict("sys.modules", {"sounddevice": fake_sd}):
                result = await engine._record(stop_event)

            assert result == b""

        asyncio.run(scenario())

    def test_mic_open_failure_raises_runtime_error(self):
        """A failure opening the input stream is wrapped as RuntimeError."""

        async def scenario():
            engine = VoiceEngine()
            fake_sd = MagicMock()
            fake_sd.InputStream.side_effect = OSError("no device")

            with patch.dict("sys.modules", {"sounddevice": fake_sd}):
                with pytest.raises(RuntimeError, match="Cannot open microphone"):
                    await engine._record(asyncio.Event())

        asyncio.run(scenario())


class TestVoskTranscriber:
    """Tests for the offline Vosk backend factory."""

    def _patch_local_model(self):
        return (
            patch("zrb.llm.voice.engine._get_vosk_model_dir", return_value="/models/m"),
            patch("os.path.isdir", return_value=True),
        )

    def test_transcribe_accept_waveform(self):
        engine = VoiceEngine()
        rec = MagicMock()
        rec.AcceptWaveform.return_value = True
        rec.Result.return_value = '{"text": "hello world"}'
        fake_vosk = MagicMock()
        fake_vosk.KaldiRecognizer = MagicMock(return_value=rec)
        p_dir, p_isdir = self._patch_local_model()
        with patch.dict("sys.modules", {"vosk": fake_vosk}), p_dir, p_isdir:
            transcribe = asyncio_run(engine._make_vosk_transcriber())
            assert asyncio_run(transcribe(b"audio")) == "hello world"

    def test_transcribe_final_result_branch(self):
        engine = VoiceEngine()
        rec = MagicMock()
        rec.AcceptWaveform.return_value = False
        rec.FinalResult.return_value = '{"text": "final text"}'
        fake_vosk = MagicMock()
        fake_vosk.KaldiRecognizer = MagicMock(return_value=rec)
        p_dir, p_isdir = self._patch_local_model()
        with patch.dict("sys.modules", {"vosk": fake_vosk}), p_dir, p_isdir:
            transcribe = asyncio_run(engine._make_vosk_transcriber())
            assert asyncio_run(transcribe(b"audio")) == "final text"

    def test_downloads_when_no_local_model(self):
        engine = VoiceEngine()
        fake_vosk = MagicMock()
        with (
            patch.dict("sys.modules", {"vosk": fake_vosk}),
            patch("zrb.llm.voice.engine._get_vosk_model_dir", return_value=None),
            patch(
                "zrb.llm.voice.engine._download_vosk_model",
                new_callable=AsyncMock,
                return_value="/dl/m",
            ) as mock_dl,
        ):
            asyncio_run(engine._make_vosk_transcriber())
            mock_dl.assert_awaited_once()

    def test_import_error_on_macos(self):
        engine = VoiceEngine()
        with (
            patch.dict("sys.modules", {"vosk": None}),
            patch("platform.system", return_value="Darwin"),
        ):
            with pytest.raises(ImportError, match="macOS"):
                asyncio_run(engine._make_vosk_transcriber())

    def test_import_error_on_linux(self):
        engine = VoiceEngine()
        with (
            patch.dict("sys.modules", {"vosk": None}),
            patch("platform.system", return_value="Linux"),
        ):
            with pytest.raises(ImportError, match="vosk is not installed"):
                asyncio_run(engine._make_vosk_transcriber())

    def test_model_load_failure_raises(self):
        engine = VoiceEngine()
        fake_vosk = MagicMock()
        fake_vosk.Model.side_effect = RuntimeError("bad model")
        p_dir, p_isdir = self._patch_local_model()
        with patch.dict("sys.modules", {"vosk": fake_vosk}), p_dir, p_isdir:
            with pytest.raises(RuntimeError, match="Vosk model not found"):
                asyncio_run(engine._make_vosk_transcriber())


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
        with patch.dict("sys.modules", {"openai": fake_openai}):
            transcribe = engine._make_openai_transcriber()
            assert asyncio_run(transcribe(b"\x00\x01")) == "openai text"

    def test_import_error(self):
        engine = VoiceEngine()
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError, match="openai is not installed"):
                engine._make_openai_transcriber()


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
        with self._patch_genai(response):
            transcribe = engine._make_google_transcriber()
            assert asyncio_run(transcribe(b"\x00\x01")) == "google text"

    def test_transcribe_empty_text(self):
        engine = VoiceEngine()
        response = MagicMock()
        response.text = None
        with self._patch_genai(response):
            transcribe = engine._make_google_transcriber()
            assert asyncio_run(transcribe(b"\x00\x01")) == ""

    def test_import_error(self):
        engine = VoiceEngine()
        with patch.dict("sys.modules", {"google": None}):
            with pytest.raises(ImportError, match="google-genai is not installed"):
                engine._make_google_transcriber()


class TestGetTranscriberDispatch:
    """The mode dispatch in _get_transcriber resolves the right factory."""

    def test_dispatches_openai(self):
        engine = VoiceEngine()
        sentinel = AsyncMock()
        with (
            patch.object(engine, "_make_openai_transcriber", return_value=sentinel),
            patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "openai"}),
        ):
            assert asyncio_run(engine._get_transcriber()) is sentinel

    def test_dispatches_google(self):
        engine = VoiceEngine()
        sentinel = AsyncMock()
        with (
            patch.object(engine, "_make_google_transcriber", return_value=sentinel),
            patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "google"}),
        ):
            assert asyncio_run(engine._get_transcriber()) is sentinel


class TestMultimodalCapabilityGate:
    """The multimodal backend rejects models that can't accept audio."""

    def test_unsupported_modality_rejected(self):
        engine = VoiceEngine()
        engine._transcriber = None
        with (
            patch("zrb.llm.config.config.llm_config") as mock_cfg,
            patch("zrb.llm.util.capabilities.model_capabilities") as mock_caps,
            patch.dict(os.environ, {"ZRB_LLM_VOICE_MODE": "multimodal"}),
        ):
            mock_cfg.multimodal_model = "gemini:gemini-2.5-flash"
            mock_cfg.resolve_model.return_value = "gemini:gemini-2.5-flash"
            mock_caps.supports_modality.return_value = False
            with pytest.raises(RuntimeError, match="does not support audio"):
                asyncio_run(engine._get_transcriber())


class TestEngineHelpers:
    """Tests for module-level helper functions."""

    def test_is_openai_chat_model_strings(self):
        from zrb.llm.voice.engine import _is_openai_chat_model

        assert _is_openai_chat_model("openai:gpt-4o") is True
        assert _is_openai_chat_model("gpt-4o") is True
        assert _is_openai_chat_model("o1-mini") is True
        assert _is_openai_chat_model("gemini-2.5-flash") is False
        assert _is_openai_chat_model(123) is False

    def test_is_openai_chat_model_instance(self):
        from zrb.llm.voice.engine import _is_openai_chat_model

        class FakeModel:
            pass

        fake_mod = MagicMock()
        fake_mod.OpenAIChatModel = FakeModel
        fake_mod.OpenAIModel = FakeModel
        with patch.dict("sys.modules", {"pydantic_ai.models.openai": fake_mod}):
            assert _is_openai_chat_model(FakeModel()) is True

    def test_is_openai_chat_model_import_fallback(self):
        from zrb.llm.voice.engine import _is_openai_chat_model

        with patch.dict("sys.modules", {"pydantic_ai.models.openai": None}):
            assert _is_openai_chat_model("openai:foo") is True
            assert _is_openai_chat_model("bar") is False

    def test_model_name_variants(self):
        from zrb.llm.voice.engine import _model_name

        assert _model_name("gpt-4o") == "gpt-4o"

        obj = MagicMock()
        obj.model_name = "the-model"
        assert _model_name(obj) == "the-model"

        class NoName:
            model_name = None
            name = None

        assert _model_name(NoName()) == "NoName"

    def test_get_vosk_model_dir_cache_hit(self):
        from zrb.llm.voice.engine import _get_vosk_model_dir

        with patch("os.path.isdir", side_effect=lambda p: p.endswith("mymodel")):
            assert _get_vosk_model_dir("mymodel").endswith("mymodel")

    def test_get_vosk_model_dir_env_hit(self):
        from zrb.llm.voice.engine import _get_vosk_model_dir

        with (
            patch("os.path.isdir", side_effect=lambda p: p == "/env/model"),
            patch.dict(os.environ, {"VOSK_MODEL_PATH": "/env/model"}),
        ):
            assert _get_vosk_model_dir("missing") == "/env/model"

    def test_get_vosk_model_dir_none(self):
        from zrb.llm.voice.engine import _get_vosk_model_dir

        with (
            patch("os.path.isdir", return_value=False),
            patch.dict(os.environ, {}, clear=True),
        ):
            assert _get_vosk_model_dir("missing") is None


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
                asyncio_run(_download_vosk_model("m", "http://host"))
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
                asyncio_run(_download_vosk_model("m", "http://host"))


def asyncio_run(coro):
    """Helper to run a coroutine synchronously in tests."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
