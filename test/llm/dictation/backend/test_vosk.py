import asyncio
import os
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.dictation.backend.vosk import (
    VoskDictationBackend,
    download_vosk_model,
    get_vosk_model_dir,
)

MODULE = "zrb.llm.dictation.backend.vosk"


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
        mock_download.assert_awaited_once_with("m", "http://host", 120.0)
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
        dl.assert_awaited_once_with("m", "http://host", 120.0)
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


def _response(*chunks):
    resp = MagicMock()
    resp.read.side_effect = list(chunks)
    return resp


def _zip(members):
    fake_zip = MagicMock()
    fake_zip.__enter__.return_value = fake_zip
    fake_zip.namelist.return_value = members
    return fake_zip


class TestDownloadVoskModel:
    @pytest.mark.asyncio
    async def test_reads_body_in_chunks_then_extracts(self):
        resp = _response(b"PK\x03\x04", b"payload", b"")
        fake_zip = _zip(["model-x/conf.json", "model-x/am/final.mdl"])
        with (
            patch("urllib.request.urlopen", return_value=resp) as urlopen,
            patch("zipfile.ZipFile", return_value=fake_zip) as zip_cls,
            patch("os.makedirs"),
            patch("os.path.isdir", return_value=True),
        ):
            result = await download_vosk_model("model-x", "http://host")

        assert result.endswith(os.path.join("vosk", "model-x"))
        assert urlopen.call_args.args[0] == "http://host/model-x.zip"
        assert resp.read.call_count == 3
        assert zip_cls.call_args.args[0].getvalue() == b"PK\x03\x04payload"
        fake_zip.extractall.assert_called_once()
        resp.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_open_failure_raises_guidance(self):
        with (
            patch("urllib.request.urlopen", side_effect=OSError("refused")),
            patch("os.makedirs"),
        ):
            with pytest.raises(RuntimeError, match="Failed to download Vosk model"):
                await download_vosk_model("m", "http://host")

    @pytest.mark.asyncio
    async def test_read_failure_raises_and_closes(self):
        resp = MagicMock()
        resp.read.side_effect = OSError("read broke")
        with (
            patch("urllib.request.urlopen", return_value=resp),
            patch("os.makedirs"),
        ):
            with pytest.raises(RuntimeError, match="Failed to download Vosk model"):
                await download_vosk_model("m", "http://host")
        resp.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_dir_after_extract_raises(self):
        with (
            patch("urllib.request.urlopen", return_value=_response(b"d", b"")),
            patch("zipfile.ZipFile", return_value=_zip(["m/x"])),
            patch("os.makedirs"),
            patch("os.path.isdir", return_value=False),
        ):
            with pytest.raises(RuntimeError, match="did not produce expected"):
                await download_vosk_model("m", "http://host")

    @pytest.mark.asyncio
    async def test_rejects_zip_slip_member_path(self):
        fake_zip = _zip(["../../etc/passwd"])
        with (
            patch("urllib.request.urlopen", return_value=_response(b"d", b"")),
            patch("zipfile.ZipFile", return_value=fake_zip),
            patch("os.makedirs"),
        ):
            with pytest.raises(RuntimeError, match="unsafe path in archive member"):
                await download_vosk_model("m", "http://host")
        fake_zip.extractall.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancellation_aborts_and_closes_socket(self):
        release = threading.Event()
        resp = MagicMock()
        resp.read.side_effect = lambda _n: release.wait(timeout=5) and b""
        with (
            patch("urllib.request.urlopen", return_value=resp),
            patch("os.makedirs"),
        ):
            task = asyncio.create_task(download_vosk_model("m", "http://host"))
            await asyncio.sleep(0.1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            resp.close.assert_called_once()
            release.set()


def _zip_of(files: dict[str, bytes]) -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class _Response:
    def __init__(self, body: bytes):
        import io

        self._body = io.BytesIO(body)

    def read(self, size):
        return self._body.read(size)

    def close(self):
        pass


@pytest.mark.asyncio
async def test_download_moves_a_complete_model_into_place(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    body = _zip_of({"m/conf/model.conf": b"ok"})
    seen_timeouts = []

    def urlopen(url, timeout=None):
        seen_timeouts.append(timeout)
        return _Response(body)

    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    path = await download_vosk_model("m", "http://host", timeout=0)

    cache = tmp_path / ".cache" / "vosk"
    assert path == str(cache / "m")
    assert (cache / "m" / "conf" / "model.conf").read_bytes() == b"ok"
    # Nothing is left of the staging directory, and 0 means no limit.
    assert [p.name for p in cache.iterdir()] == ["m"]
    assert seen_timeouts == [None]


@pytest.mark.asyncio
async def test_a_model_another_session_installed_first_is_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    installed = tmp_path / ".cache" / "vosk" / "m"
    installed.mkdir(parents=True)
    (installed / "marker").write_bytes(b"first")
    body = _zip_of({"m/marker": b"second"})
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda url, timeout=None: _Response(body)
    )

    await download_vosk_model("m", "http://host")

    assert (installed / "marker").read_bytes() == b"first"
    assert [p.name for p in installed.parent.iterdir()] == ["m"]
