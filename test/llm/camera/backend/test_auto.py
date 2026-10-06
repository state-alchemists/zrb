'`AutoCameraBackend`: Termux:API first on Android, then ffmpeg per platform.'

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.camera.backend import (
    AutoCameraBackend,
    FfmpegCameraBackend,
    TermuxCameraBackend,
)


@pytest.fixture
def clean_env(monkeypatch):
    'Strip every camera-relevant env var before each test.'
    for var in ("WSL_DISTRO_NAME", "WSLENV"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class _FakeProcess:
    'Minimal async-process stand-in for `asyncio.create_subprocess_exec`.'

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
async def test_termux_camera_photo_returns_bytes(clean_env, tmp_path):
    "The capture path is Termux's real home dir, not tempfile.gettempdir() --"
    payload = b"\xff\xd8\xff-fake-jpeg"
    fake_path = str(tmp_path / "photo.jpg")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr("shutil.which", _which_only("termux-camera-photo"))

    def _make_proc(*args, **kwargs):

        path = args[-1]
        with open(path, "wb") as fh:
            fh.write(payload)
        return _FakeProcess()

    backend = AutoCameraBackend(termux=TermuxCameraBackend(fake_path))
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await backend.capture(None)

    assert result == payload

    assert not os.path.exists(fake_path)


@pytest.mark.asyncio
async def test_termux_camera_photo_uses_device_as_camera_id(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr("shutil.which", _which_only("termux-camera-photo"))

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess()

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        await AutoCameraBackend().capture("1")

    assert seen_cmds[0] == ["termux-camera-photo", "-c", "1", seen_cmds[0][-1]]


@pytest.mark.asyncio
async def test_termux_falls_through_to_ffmpeg_when_no_file_written(clean_env):
    'termux-camera-photo ran but wrote nothing; ffmpeg is also unavailable.'
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr("shutil.which", _which_only("termux-camera-photo"))

    with patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=_FakeProcess())
    ):
        result = await AutoCameraBackend().capture(None)

    assert result is None


@pytest.mark.asyncio
async def test_termux_skips_camera_photo_when_binary_missing(clean_env):
    "is_termux() is True, but termux-camera-photo isn't on PATH (e.g. proot)."
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr("shutil.which", _which_only())

    result = await AutoCameraBackend().capture(None)

    assert result is None


@pytest.mark.asyncio
async def test_ffmpeg_missing_returns_none(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only())

    result = await AutoCameraBackend().capture(None)

    assert result is None


@pytest.mark.asyncio
async def test_macos_ffmpeg_avfoundation_capture(clean_env):
    clean_env.setattr("sys.platform", "darwin")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    payload = b"\xff\xd8\xff-jpeg"

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess(stdout=payload)

    backend = AutoCameraBackend()
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await backend.capture(None)

    assert result == payload
    cmd = seen_cmds[0]
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "avfoundation"
    assert "-i" in cmd and cmd[cmd.index("-i") + 1] == "0"


@pytest.mark.asyncio
async def test_linux_ffmpeg_v4l2_default_device(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    payload = b"\xff\xd8\xff-jpeg"

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess(stdout=payload)

    backend = AutoCameraBackend()
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await backend.capture(None)

    assert result == payload
    cmd = seen_cmds[0]
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "v4l2"
    assert "-i" in cmd and cmd[cmd.index("-i") + 1] == "/dev/video0"


@pytest.mark.asyncio
async def test_linux_ffmpeg_tries_mjpeg_before_raw_fallback(clean_env):
    'v4l2 requests MJPEG@640x480 first -- see camera.py module docstring for why.'
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    payload = b"\xff\xd8\xff-jpeg"

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess(stdout=payload)

    backend = AutoCameraBackend()
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await backend.capture(None)

    assert result == payload

    assert len(seen_cmds) == 1
    cmd = seen_cmds[0]
    assert cmd[cmd.index("-input_format") + 1] == "mjpeg"
    assert cmd[cmd.index("-video_size") + 1] == "640x480"


@pytest.mark.asyncio
async def test_linux_ffmpeg_falls_back_to_raw_when_mjpeg_unsupported(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    payload = b"\xff\xd8\xff-jpeg"

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        cmd = list(args)
        seen_cmds.append(cmd)
        if "-input_format" in cmd:
            return _FakeProcess(stderr=b"mjpeg not supported", returncode=1)
        return _FakeProcess(stdout=payload)

    backend = AutoCameraBackend()
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await backend.capture(None)

    assert result == payload
    assert len(seen_cmds) == 2
    assert "-input_format" not in seen_cmds[1]


@pytest.mark.asyncio
async def test_linux_ffmpeg_explicit_device_overrides_default(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess(stdout=b"jpeg")

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        await AutoCameraBackend().capture("/dev/video2")

    cmd = seen_cmds[0]
    assert cmd[cmd.index("-i") + 1] == "/dev/video2"


@pytest.mark.asyncio
async def test_windows_ffmpeg_uses_explicit_device_name(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess(stdout=b"jpeg")

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await AutoCameraBackend().capture("USB2.0 Camera")

    assert result == b"jpeg"

    assert len(seen_cmds) == 1
    cmd = seen_cmds[0]
    assert cmd[cmd.index("-f") + 1] == "dshow"
    assert cmd[cmd.index("-i") + 1] == "video=USB2.0 Camera"


@pytest.mark.asyncio
async def test_a_failed_termux_capture_never_returns_an_earlier_photo(
    clean_env, tmp_path
):
    stale = tmp_path / "photo.jpg"
    stale.write_bytes(b"old photo")
    clean_env.setattr("shutil.which", _which_only("termux-camera-photo"))

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=lambda *a, **k: _FakeProcess(returncode=1)),
    ):
        result = await TermuxCameraBackend(str(stale)).capture(None)

    assert result is None
    assert not stale.exists()


@pytest.mark.asyncio
async def test_each_termux_capture_writes_its_own_file(clean_env):
    clean_env.setattr("shutil.which", _which_only("termux-camera-photo"))
    paths: list[str] = []

    def _make_proc(*args, **kwargs):
        paths.append(args[-1])
        return _FakeProcess()

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        backend = TermuxCameraBackend()
        await backend.capture(None)
        await backend.capture(None)

    assert len(set(paths)) == 2
    assert all("_camera_" in path for path in paths)


@pytest.mark.asyncio
async def test_a_capture_that_never_runs_ffmpeg_drops_the_last_error(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    backend = FfmpegCameraBackend()
    failed = _FakeProcess(stderr=b"device busy", returncode=1)
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=failed)):
        await backend.capture(None)
    assert backend.last_error == "device busy"

    clean_env.setattr("shutil.which", _which_only())
    await backend.capture(None)

    assert backend.last_error is None


@pytest.mark.asyncio
async def test_an_unreadable_termux_photo_is_a_failed_capture(clean_env, tmp_path):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr("shutil.which", _which_only("termux-camera-photo"))
    unreadable = tmp_path / "photo.jpg"

    async def _write_a_directory(*args, **kwargs):
        unreadable.mkdir()
        return _FakeProcess()

    with patch("asyncio.create_subprocess_exec", new=_write_a_directory):
        result = await TermuxCameraBackend(str(unreadable)).capture(None)

    assert result is None
