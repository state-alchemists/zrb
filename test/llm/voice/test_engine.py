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


def asyncio_run(coro):
    """Helper to run a coroutine synchronously in tests."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
