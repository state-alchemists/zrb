"`AutoCameraBackend` and its backends: one deadline for a whole capture, and"

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.camera.backend import (
    AutoCameraBackend,
    FfmpegCameraBackend,
    TermuxCameraBackend,
)


@pytest.fixture
def clean_env(monkeypatch):
    "Strip every camera-relevant env var before each test."
    for var in ("WSL_DISTRO_NAME", "WSLENV"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class _FakeProcess:
    "Minimal async-process stand-in for `asyncio.create_subprocess_exec`."

    def __init__(
        self,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        hang_seconds: float = 0,
    ):
        self._stdout = stdout
        self._stderr = stderr

        self._exit_code = returncode
        self.returncode: int | None = None
        self._hang_seconds = hang_seconds
        self.killed = False

    async def communicate(self):
        if self._hang_seconds:
            await asyncio.sleep(self._hang_seconds)
        self.returncode = self._exit_code
        return (self._stdout, self._stderr)

    def kill(self):
        self.killed = True
        self.returncode = -9

    async def wait(self):
        return self.returncode


def _which_only(*names: str):
    'Return a `shutil.which` stand-in that only "finds" the given names.'

    def _which(name: str):
        return f"/usr/bin/{name}" if name in names else None

    return _which


@pytest.mark.asyncio
async def test_capture_timeout_returns_none_with_hint(clean_env):
    "A hung ffmpeg (open camera, no frame ever delivered) times out instead"
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))

    hung_procs: list[_FakeProcess] = []

    def _make_proc(*args, **kwargs):
        proc = _FakeProcess(stdout=b"jpeg", hang_seconds=10)
        hung_procs.append(proc)
        return proc

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        backend = AutoCameraBackend(ffmpeg=FfmpegCameraBackend(timeout=0.05))
        result = await backend.capture(None)

    assert result is None
    assert all(proc.killed for proc in hung_procs)
    assert "timed out" in backend.get_failure_hint()


@pytest.mark.asyncio
async def test_a_hung_termux_capture_is_abandoned_after_the_timeout(
    clean_env, tmp_path
):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr("shutil.which", _which_only("termux-camera-photo"))
    hung: list[_FakeProcess] = []

    def _make_proc(*args, **kwargs):
        proc = _FakeProcess(hang_seconds=10)
        hung.append(proc)
        return proc

    backend = TermuxCameraBackend(str(tmp_path / "photo.jpg"), timeout=0.05)
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await backend.capture(None)

    assert result is None
    assert [proc.killed for proc in hung] == [True]


@pytest.mark.asyncio
async def test_an_mjpeg_attempt_that_times_out_leaves_no_time_for_the_raw_one(
    clean_env,
):
    "Both ffmpeg attempts share one deadline: a 0.05 s timeout never"
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    started: list[_FakeProcess] = []

    def _make_proc(*args, **kwargs):
        proc = _FakeProcess(hang_seconds=10)
        started.append(proc)
        return proc

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await FfmpegCameraBackend(timeout=0.05).capture(None)

    assert result is None
    assert len(started) == 1


@pytest.mark.asyncio
async def test_auto_shares_one_deadline_between_termux_and_ffmpeg(clean_env, tmp_path):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr("shutil.which", _which_only("termux-camera-photo", "ffmpeg"))
    started: list[_FakeProcess] = []

    def _make_proc(*args, **kwargs):
        proc = _FakeProcess(hang_seconds=10)
        started.append(proc)
        return proc

    backend = AutoCameraBackend(
        termux=TermuxCameraBackend(str(tmp_path / "p.jpg")), timeout=0.05
    )
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await backend.capture(None)

    assert result is None
    assert len(started) == 1


@pytest.mark.asyncio
async def test_windows_device_detection_stays_inside_the_deadline(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    started: list[_FakeProcess] = []

    def _make_proc(*args, **kwargs):
        proc = _FakeProcess(hang_seconds=10)
        started.append(proc)
        return proc

    loop = asyncio.get_running_loop()
    begin = loop.time()
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await FfmpegCameraBackend(timeout=0.05).capture(None)

    assert result is None
    assert loop.time() - begin < 1
    assert len(started) == 1


async def _cancel_capture(capture) -> None:
    task = asyncio.create_task(capture)
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_a_cancelled_ffmpeg_capture_kills_ffmpeg(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    hung: list[_FakeProcess] = []

    def _make_proc(*args, **kwargs):
        proc = _FakeProcess(stdout=b"jpeg", hang_seconds=10)
        hung.append(proc)
        return proc

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        await _cancel_capture(FfmpegCameraBackend(timeout=5).capture(None))

    assert [proc.killed for proc in hung] == [True]


@pytest.mark.asyncio
async def test_a_cancelled_termux_capture_kills_termux_camera_photo(
    clean_env, tmp_path
):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr("shutil.which", _which_only("termux-camera-photo"))
    hung: list[_FakeProcess] = []

    def _make_proc(*args, **kwargs):
        proc = _FakeProcess(hang_seconds=10)
        hung.append(proc)
        return proc

    backend = TermuxCameraBackend(str(tmp_path / "photo.jpg"), timeout=5)
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        await _cancel_capture(backend.capture(None))

    assert [proc.killed for proc in hung] == [True]


@pytest.mark.asyncio
async def test_a_cancelled_windows_device_listing_kills_ffmpeg(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    hung: list[_FakeProcess] = []

    def _make_proc(*args, **kwargs):
        proc = _FakeProcess(hang_seconds=10)
        hung.append(proc)
        return proc

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        await _cancel_capture(FfmpegCameraBackend(timeout=5).capture(None))

    assert [proc.killed for proc in hung] == [True]


@pytest.mark.asyncio
async def test_a_negative_timeout_means_no_limit(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=b"jpeg")),
    ):
        result = await FfmpegCameraBackend(timeout=-1).capture(None)

    assert result == b"jpeg"
