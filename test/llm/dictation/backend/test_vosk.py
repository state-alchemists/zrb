import asyncio
import json
import os
import threading
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from zrb.llm.dictation.backend.vosk import (
    VoskDictationBackend,
    VoskDownloadLimits,
    get_vosk_model_dir,
)

MODULE = "zrb.llm.dictation.backend.vosk"


def _payload(*words: tuple[str, float], text: str = "") -> str:
    """A vosk result carrying the confidences given, as (word, conf) pairs."""
    result = [{"word": word, "conf": conf} for word, conf in words]
    if not text:
        text = " ".join(word for word, _ in words)
    return json.dumps({"text": text, "result": result})


def _fake_vosk(accept=True, result='{"text": "hello world"}'):
    recognizer = MagicMock()
    recognizer.AcceptWaveform.return_value = accept
    recognizer.Result.return_value = result
    recognizer.FinalResult.return_value = result
    fake_vosk = MagicMock()
    fake_vosk.KaldiRecognizer = MagicMock(return_value=recognizer)
    return fake_vosk


def _local_model(path="/models/m"):
    return patch(f"{MODULE}.get_vosk_model_dir", return_value=path)


class TestVoskBackend:
    def test_name_is_vosk(self):
        assert VoskDictationBackend().name == "vosk"

    def test_is_model_downloaded_follows_model_dir(self):
        backend = VoskDictationBackend("m", "http://host")
        with _local_model("/models/m"):
            assert backend.is_model_downloaded is True
        with _local_model(None):
            assert backend.is_model_downloaded is False

    @pytest.mark.asyncio
    async def test_transcribe_accept_waveform_uses_result(self):
        fake_vosk = _fake_vosk(accept=True)
        backend = VoskDictationBackend("m", "http://host")
        with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
            assert await backend.transcribe(b"audio") == "hello world"
        fake_vosk.Model.assert_called_once_with("/models/m")
        fake_vosk.KaldiRecognizer.assert_called_once_with(
            fake_vosk.Model.return_value, 16000
        )

    @pytest.mark.asyncio
    async def test_transcribe_falls_back_to_final_result(self):
        fake_vosk = _fake_vosk(accept=False, result='{"text": "final text"}')
        backend = VoskDictationBackend("m", "http://host")
        with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
            assert await backend.transcribe(b"audio") == "final text"

    @pytest.mark.asyncio
    async def test_hands_free_drops_a_faintly_heard_transcript(self):
        fake_vosk = _fake_vosk(result=_payload(("hello", 0.2), ("there", 0.3)))
        backend = VoskDictationBackend("m", "http://host", confidence=0.5)
        with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
            assert await backend.transcribe_speech(b"audio") == ""

    @pytest.mark.asyncio
    async def test_hands_free_keeps_a_clearly_heard_transcript(self):
        fake_vosk = _fake_vosk(result=_payload(("hello", 0.9), ("there", 0.8)))
        backend = VoskDictationBackend("m", "http://host", confidence=0.5)
        with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
            assert await backend.transcribe_speech(b"audio") == "hello there"

    @pytest.mark.asyncio
    async def test_push_to_talk_keeps_every_word_however_faintly_heard(self):
        fake_vosk = _fake_vosk(result=_payload(("hello", 0.1)))
        backend = VoskDictationBackend("m", "http://host", confidence=0.9)
        with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
            assert await backend.transcribe(b"audio") == "hello"

    @pytest.mark.asyncio
    async def test_hands_free_without_a_floor_keeps_a_faint_transcript(self):
        fake_vosk = _fake_vosk(result=_payload(("hello", 0.1)))
        backend = VoskDictationBackend("m", "http://host")
        with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
            assert await backend.transcribe_speech(b"audio") == "hello"

    @pytest.mark.asyncio
    async def test_transcribe_decodes_off_the_event_loop_thread(self):
        fake_vosk = _fake_vosk()
        recognizer = fake_vosk.KaldiRecognizer.return_value
        decoded_on = []
        recognizer.AcceptWaveform.side_effect = lambda audio: (
            decoded_on.append(threading.get_ident()) or True
        )
        backend = VoskDictationBackend("m", "http://host")
        with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
            await backend.transcribe(b"audio")
        assert decoded_on and decoded_on[0] != threading.get_ident()

    @pytest.mark.asyncio
    async def test_model_loaded_once_across_transcriptions(self):
        fake_vosk = _fake_vosk()
        backend = VoskDictationBackend("m", "http://host")
        with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
            await backend.transcribe(b"a")
            await backend.transcribe(b"b")
        fake_vosk.Model.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_downloads_missing_model(self):
        fake_vosk = _fake_vosk()
        backend = VoskDictationBackend("m", "http://host")
        with (
            patch.dict("sys.modules", {"vosk": fake_vosk}),
            _local_model(None),
            patch(
                f"{MODULE}.download_vosk_model",
                new_callable=AsyncMock,
                return_value="/dl/m",
            ) as mock_download,
        ):
            await backend.transcribe(b"a")
        mock_download.assert_awaited_once_with("m", "http://host", 120.0, ANY)
        fake_vosk.Model.assert_called_once_with("/dl/m")

    @pytest.mark.parametrize(
        "system, message", [("Darwin", "macOS"), ("Linux", "vosk is not installed")]
    )
    @pytest.mark.asyncio
    async def test_missing_vosk_raises_platform_hint(self, system, message):
        backend = VoskDictationBackend()
        with (
            patch.dict("sys.modules", {"vosk": None}),
            patch("platform.system", return_value=system),
        ):
            with pytest.raises(RuntimeError, match=message):
                await backend.transcribe(b"a")

    @pytest.mark.asyncio
    async def test_model_load_failure_raises_guidance(self):
        fake_vosk = _fake_vosk()
        fake_vosk.Model.side_effect = RuntimeError("bad model")
        backend = VoskDictationBackend("m", "http://host")
        with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
            with pytest.raises(RuntimeError, match="Vosk model not found"):
                await backend.transcribe(b"a")

    @pytest.mark.asyncio
    async def test_prepare_skips_when_model_present(self):
        report = MagicMock()
        with (
            _local_model(),
            patch(f"{MODULE}.download_vosk_model", new_callable=AsyncMock) as dl,
        ):
            await VoskDictationBackend().prepare(report)
        dl.assert_not_awaited()
        report.assert_not_called()

    @pytest.mark.asyncio
    async def test_prepare_downloads_and_reports_progress(self):
        report = MagicMock()
        with (
            _local_model(None),
            patch(f"{MODULE}.download_vosk_model", new_callable=AsyncMock) as dl,
        ):
            await VoskDictationBackend("m", "http://host").prepare(report)
        dl.assert_awaited_once_with("m", "http://host", 120.0, ANY)
        assert [c.args[0] for c in report.call_args_list] == [
            "Downloading the voice model...",
            "Voice model ready",
        ]


class TestGetVoskModelDir:
    def test_cache_hit(self):
        with patch("os.path.isdir", side_effect=lambda p: p.endswith("mymodel")):
            assert get_vosk_model_dir("mymodel").endswith("mymodel")

    def test_env_hit(self):
        with (
            patch("os.path.isdir", side_effect=lambda p: p == "/env/model"),
            patch.dict(os.environ, {"VOSK_MODEL_PATH": "/env/model"}),
        ):
            assert get_vosk_model_dir("missing") == "/env/model"

    def test_none(self):
        with (
            patch("os.path.isdir", return_value=False),
            patch.dict(os.environ, {}, clear=True),
        ):
            assert get_vosk_model_dir("missing") is None


class FakeRecognizer:
    """Finishes a phrase on each chunk of b"." and hears the rest as partial."""

    def __init__(self):
        self.heard = b""

    def AcceptWaveform(self, audio):
        self.heard += audio
        return audio == b"."

    def Result(self):
        phrase, self.heard = self.heard.rstrip(b".").decode(), b""
        return f'{{"text": "{phrase}"}}'

    def PartialResult(self):
        return f'{{"partial": "{self.heard.decode()}"}}'

    def FinalResult(self):
        phrase, self.heard = self.heard.decode(), b""
        return f'{{"text": "{phrase}"}}'


@pytest.mark.asyncio
async def test_a_vosk_stream_transcribes_while_fed():
    fake_vosk = MagicMock()
    fake_vosk.KaldiRecognizer = MagicMock(return_value=FakeRecognizer())
    backend = VoskDictationBackend("m", "http://host")
    with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
        stream = await backend.create_stream()

    await stream.feed(b"open")
    assert stream.partial == "open"
    await stream.feed(b".")
    await stream.feed(b"the file")
    assert stream.partial == "open the file"
    assert await stream.finish() == "open the file"


class ConfidentRecognizer(FakeRecognizer):
    """As `FakeRecognizer`, reporting a confidence for the words it heard."""

    def __init__(self, conf=0.9):
        super().__init__()
        self._conf = conf

    def Result(self):
        phrase, self.heard = self.heard.rstrip(b".").decode(), b""
        return _payload((phrase, self._conf), text=phrase)

    def FinalResult(self):
        phrase, self.heard = self.heard.decode(), b""
        return _payload((phrase, self._conf), text=phrase)


async def _confident_stream(conf, confidence_floor):
    fake_vosk = MagicMock()
    fake_vosk.KaldiRecognizer = MagicMock(return_value=ConfidentRecognizer(conf))
    backend = VoskDictationBackend("m", "http://host", confidence=confidence_floor)
    with patch.dict("sys.modules", {"vosk": fake_vosk}), _local_model():
        return await backend.create_stream()


@pytest.mark.asyncio
async def test_a_faintly_heard_stream_is_dropped_at_the_end():
    """The words are shown while they are heard; it is the finished transcript
    that has to be words, not just sound."""
    stream = await _confident_stream(conf=0.2, confidence_floor=0.5)

    await stream.feed(b"open")

    assert stream.partial == "open"
    assert await stream.finish() == ""


@pytest.mark.asyncio
async def test_a_clearly_heard_stream_reaches_the_end():
    stream = await _confident_stream(conf=0.9, confidence_floor=0.5)

    await stream.feed(b"open")

    assert await stream.finish() == "open"
