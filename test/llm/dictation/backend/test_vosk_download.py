"""Downloading and unpacking a Vosk model: what it costs, and what it leaves
behind."""

import asyncio
import io
import os
import struct
import threading
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.dictation.backend.vosk import (
    VoskDictationBackend,
    VoskDownloadLimits,
    download_vosk_model,
)

MB = 1 << 20
KNOB = "ZRB_LLM_DICTATION_VOSK"


def _limits(**kwargs):
    """Every limit in megabytes, so a test names the size it is about."""
    return VoskDownloadLimits(**{name: megabytes for name, megabytes in kwargs.items()})


def _zip_of(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class _Response:
    """A response that serves a real body, so nothing stands in for the file
    the download writes and then hands to `zipfile`."""

    def __init__(self, body: bytes):
        self._body = io.BytesIO(body)

    def read(self, size):
        return self._body.read(size)

    def close(self):
        pass


def _zip_lying_about_its_size(path: str, declared: int, real: int) -> str:
    """A zip file whose directory says *declared* bytes about a member that
    actually holds *real* bytes of zeros — the shape of a decompression bomb,
    and of any archive whose headers are simply not to be trusted."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("model/bomb", b"\0" * real)
    raw = bytearray(buffer.getvalue())
    end = raw.rindex(b"PK\x05\x06")
    at = struct.unpack_from("<I", raw, end + 16)[0]
    while at < end:
        struct.pack_into("<I", raw, at + 24, declared)
        name, extra, comment = struct.unpack_from("<HHH", raw, at + 28)
        at += 46 + name + extra + comment
    struct.pack_into("<I", raw, 22, declared)
    with open(path, "wb") as handle:
        handle.write(bytes(raw))
    return path


@pytest.mark.usefixtures("tmp_home")
class TestDownloadVoskModel:
    @pytest.mark.asyncio
    async def test_streams_the_body_to_a_file_then_extracts_it(
        self, fake_response, fake_zip
    ):
        resp = fake_response(b"PK\x03\x04", b"payload", b"")
        archive = fake_zip(["model-x/conf.json", "model-x/am/final.mdl"])
        written = {}

        def _open(path):
            # Read while it exists: the file is removed on the way out.
            with open(path, "rb") as handle:
                written["bytes"] = handle.read()
            written["path"] = path
            return archive

        with (
            patch("urllib.request.urlopen", return_value=resp) as urlopen,
            patch("zipfile.ZipFile", side_effect=_open),
            patch("os.path.isdir", return_value=True),
        ):
            result = await download_vosk_model("model-x", "http://host")

        assert result.endswith(os.path.join("vosk", "model-x"))
        assert urlopen.call_args.args[0] == "http://host/model-x.zip"
        assert resp.read.call_count == 3
        assert written["bytes"] == b"PK\x03\x04payload"
        archive.extractall.assert_called_once()
        resp.close.assert_called_once()
        assert not os.path.exists(written["path"])

    @pytest.mark.asyncio
    async def test_open_failure_raises_guidance(self):
        with (patch("urllib.request.urlopen", side_effect=OSError("refused")),):
            with pytest.raises(RuntimeError, match="Failed to download Vosk model"):
                await download_vosk_model("m", "http://host")

    @pytest.mark.asyncio
    async def test_read_failure_raises_and_closes(self):
        resp = MagicMock()
        resp.read.side_effect = OSError("read broke")
        with (patch("urllib.request.urlopen", return_value=resp),):
            with pytest.raises(RuntimeError, match="Failed to download Vosk model"):
                await download_vosk_model("m", "http://host")
        resp.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_dir_after_extract_raises(self, fake_response, fake_zip):
        with (
            patch("urllib.request.urlopen", return_value=fake_response(b"d", b"")),
            patch("zipfile.ZipFile", return_value=fake_zip(["m/x"])),
            patch("os.path.isdir", return_value=False),
        ):
            with pytest.raises(RuntimeError, match="did not produce expected"):
                await download_vosk_model("m", "http://host")

    @pytest.mark.asyncio
    async def test_rejects_zip_slip_member_path(self, fake_response, fake_zip):
        archive = fake_zip(["../../etc/passwd"])
        with (
            patch("urllib.request.urlopen", return_value=fake_response(b"d", b"")),
            patch("zipfile.ZipFile", return_value=archive),
        ):
            with pytest.raises(RuntimeError, match="unsafe path in archive member"):
                await download_vosk_model("m", "http://host")
        archive.extractall.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancellation_aborts_and_closes_socket(self):
        release = threading.Event()
        resp = MagicMock()
        resp.read.side_effect = lambda _n: release.wait(timeout=5) and b""
        with (patch("urllib.request.urlopen", return_value=resp),):
            task = asyncio.create_task(download_vosk_model("m", "http://host"))
            await asyncio.sleep(0.1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            resp.close.assert_called_once()
            release.set()


@pytest.mark.asyncio
async def test_download_moves_a_complete_model_into_place(tmp_home, monkeypatch):
    tmp_path = tmp_home
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
async def test_a_model_another_session_installed_first_is_kept(tmp_home, monkeypatch):
    tmp_path = tmp_home
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


class TestVoskDownloadLimits:
    @pytest.mark.asyncio
    async def test_a_response_larger_than_the_download_cap_is_stopped(
        self, fake_response
    ):
        resp = fake_response(b"x" * MB, b"y" * MB, b"")
        with patch("urllib.request.urlopen", return_value=resp):
            with pytest.raises(RuntimeError, match=f"{KNOB}_MAX_DOWNLOAD_MB"):
                await download_vosk_model(
                    "m", "http://host", limits=_limits(max_download_mb=1)
                )
        resp.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_the_download_file_is_removed_when_the_cap_is_hit(
        self, fake_response, fake_zip, cache_dir
    ):
        seen: list[str] = []

        def _open(path):
            seen.append(path)
            return fake_zip(["m/x"])

        with (
            patch(
                "urllib.request.urlopen",
                return_value=fake_response(b"x" * MB, b"y" * MB, b""),
            ),
            patch("zipfile.ZipFile", side_effect=_open),
        ):
            with pytest.raises(RuntimeError):
                await download_vosk_model(
                    "m", "http://host", limits=_limits(max_download_mb=1)
                )
        assert seen == [], "the cap is hit before the file is opened for reading"
        assert not [p for p in os.listdir(cache_dir) if p.endswith(".zip")]

    @pytest.mark.asyncio
    async def test_an_archive_that_unpacks_past_the_total_is_rejected(
        self, fake_response, fake_zip
    ):
        archive = fake_zip(["m/a", "m/b"], sizes={"m/a": 8 * MB, "m/b": 8 * MB})
        with (
            patch("urllib.request.urlopen", return_value=fake_response(b"d", b"")),
            patch("zipfile.ZipFile", return_value=archive),
        ):
            with pytest.raises(RuntimeError, match=f"{KNOB}_MAX_UNCOMPRESSED_MB"):
                await download_vosk_model(
                    "m", "http://host", limits=_limits(max_uncompressed_mb=10)
                )
        archive.extractall.assert_not_called()

    @pytest.mark.asyncio
    async def test_one_file_larger_than_the_per_file_cap_is_rejected(
        self, fake_response, fake_zip
    ):
        archive = fake_zip(["m/small", "m/huge"], sizes={"m/huge": 40 * MB})
        with (
            patch("urllib.request.urlopen", return_value=fake_response(b"d", b"")),
            patch("zipfile.ZipFile", return_value=archive),
        ):
            with pytest.raises(RuntimeError, match=f"{KNOB}_MAX_FILE_MB"):
                await download_vosk_model(
                    "m", "http://host", limits=_limits(max_file_mb=10)
                )
        archive.extractall.assert_not_called()

    @pytest.mark.asyncio
    async def test_more_files_than_the_file_count_cap_is_rejected(
        self, fake_response, fake_zip
    ):
        archive = fake_zip([f"m/{i}" for i in range(50)])
        with (
            patch("urllib.request.urlopen", return_value=fake_response(b"d", b"")),
            patch("zipfile.ZipFile", return_value=archive),
        ):
            with pytest.raises(RuntimeError, match=f"{KNOB}_MAX_FILES"):
                await download_vosk_model(
                    "m", "http://host", limits=_limits(max_files=10)
                )
        archive.extractall.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_limit_is_no_limit(self, fake_response, fake_zip):
        """A real acoustic model is one large file, and a 0 limit is how an
        operator says they accept that."""
        archive = fake_zip(["m/huge"], sizes={"m/huge": 64 * MB})
        with (
            patch("urllib.request.urlopen", return_value=fake_response(b"d", b"")),
            patch("zipfile.ZipFile", return_value=archive),
            patch("os.path.isdir", return_value=True),
        ):
            result = await download_vosk_model(
                "m",
                "http://host",
                limits=_limits(
                    max_download_mb=0,
                    max_uncompressed_mb=0,
                    max_file_mb=0,
                    max_files=0,
                ),
            )
        assert result.endswith(os.path.join("vosk", "m"))
        archive.extractall.assert_called_once()

    def test_the_defaults_come_from_the_knobs(self):
        assert VoskDownloadLimits().max_download == int(4096 * MB)
        assert VoskDownloadLimits().max_uncompressed == int(8192 * MB)
        assert VoskDownloadLimits().max_file == int(4096 * MB)
        assert VoskDownloadLimits().max_files == 10000

    def test_an_explicit_zero_beats_the_knob(self):
        assert VoskDownloadLimits(max_download_mb=0).max_download == 0

    @pytest.mark.asyncio
    async def test_a_backend_applies_the_limits_it_was_given(
        self, fake_response, tmp_home
    ):
        """The backend turns its keywords into a `VoskDownloadLimits`; an
        operator who builds their own should not get the defaults instead."""
        backend = VoskDictationBackend("m", "http://host", max_download_mb=1)
        with patch(
            "urllib.request.urlopen",
            return_value=fake_response(b"x" * MB, b"y" * MB, b""),
        ):
            with pytest.raises(RuntimeError, match=f"{KNOB}_MAX_DOWNLOAD_MB"):
                await backend.prepare(lambda _msg: None)

    @pytest.mark.asyncio
    async def test_a_rejected_archive_leaves_nothing_behind(
        self, fake_response, fake_zip, cache_dir
    ):
        archive = fake_zip(["m/a", "m/b"], sizes={"m/a": 8 * MB, "m/b": 8 * MB})
        with (
            patch("urllib.request.urlopen", return_value=fake_response(b"d", b"")),
            patch("zipfile.ZipFile", return_value=archive),
        ):
            with pytest.raises(RuntimeError):
                await download_vosk_model(
                    "m", "http://host", limits=_limits(max_uncompressed_mb=10)
                )
        assert os.listdir(cache_dir) == []


@pytest.mark.usefixtures("tmp_home")
class TestUntrustedArchiveHeaders:
    @pytest.mark.asyncio
    async def test_a_member_that_under_declares_its_size_writes_nothing(
        self, tmp_path, fake_response, cache_dir
    ):
        """The size limits read the archive's own directory, so they are worth
        anything only if a member cannot then write more than it declared. This
        one declares 16 bytes and holds 32 MB, and gets past every limit on the
        declared numbers — `zipfile` reads to the declared size, fails the CRC
        and writes nothing, so the backstop is the format, not the check."""
        path = _zip_lying_about_its_size(
            str(tmp_path / "liar.zip"), declared=16, real=32 * MB
        )
        with open(path, "rb") as handle:
            body = handle.read()

        with patch("urllib.request.urlopen", return_value=fake_response(body, b"")):
            with pytest.raises(zipfile.BadZipFile):
                await download_vosk_model("m", "http://host", limits=_limits())

        assert os.listdir(cache_dir) == []
