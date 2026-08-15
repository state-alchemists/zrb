"""Public-API tests for camera photo capture.

All paths exercise `get_camera_photo()` and `missing_tool_hint()`. Per
AGENTS.md, no underscore-prefixed helpers are touched directly. External
dependencies (termux-camera-photo, ffmpeg, the live filesystem) are mocked.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.util.camera import get_camera_photo, missing_tool_hint

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_env(monkeypatch):
    """Strip every camera-relevant env var before each test."""
    for var in ("WSL_DISTRO_NAME", "WSLENV"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class _FakeProcess:
    """Minimal async-process stand-in for `asyncio.create_subprocess_exec`."""

    def __init__(self, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self):
        return (self._stdout, self._stderr)


def _which_only(*names: str):
    """Return a `shutil.which` stand-in that only "finds" the given names."""

    def _which(name: str):
        return f"/usr/bin/{name}" if name in names else None

    return _which


# ---------------------------------------------------------------------------
# get_camera_photo -- Termux
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_termux_camera_photo_returns_bytes(clean_env, tmp_path):
    """The capture path is Termux's real home dir, not tempfile.gettempdir() --
    a proot-distro guest's own `/tmp` isn't visible to the Termux:API app
    process that actually writes the file. Redirect the module's fixed path
    to a writable location for this test."""
    payload = b"\xff\xd8\xff-fake-jpeg"
    fake_path = str(tmp_path / "photo.jpg")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr(
        "zrb.llm.util.camera.shutil.which", _which_only("termux-camera-photo")
    )
    clean_env.setattr("zrb.llm.util.camera._TERMUX_HOME_PHOTO_PATH", fake_path)

    def _make_proc(*args, **kwargs):
        # termux-camera-photo writes its output to the target path (last arg).
        path = args[-1]
        with open(path, "wb") as fh:
            fh.write(payload)
        return _FakeProcess()

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await get_camera_photo()

    assert result == payload
    # File is cleaned up after read.
    assert not os.path.exists(fake_path)


@pytest.mark.asyncio
async def test_termux_camera_photo_uses_device_as_camera_id(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr(
        "zrb.llm.util.camera.shutil.which", _which_only("termux-camera-photo")
    )

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess()

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        await get_camera_photo(device="1")

    assert seen_cmds[0] == ["termux-camera-photo", "-c", "1", seen_cmds[0][-1]]


@pytest.mark.asyncio
async def test_termux_falls_through_to_ffmpeg_when_no_file_written(clean_env):
    """termux-camera-photo ran but wrote nothing; ffmpeg is also unavailable."""
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr(
        "zrb.llm.util.camera.shutil.which", _which_only("termux-camera-photo")
    )

    with patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=_FakeProcess())
    ):
        result = await get_camera_photo()

    assert result is None


@pytest.mark.asyncio
async def test_termux_skips_camera_photo_when_binary_missing(clean_env):
    """is_termux() is True, but termux-camera-photo isn't on PATH (e.g. proot)."""
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only())

    result = await get_camera_photo()

    assert result is None


# ---------------------------------------------------------------------------
# get_camera_photo -- ffmpeg (macOS / Windows / Linux / WSL)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ffmpeg_missing_returns_none(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only())

    result = await get_camera_photo()

    assert result is None


@pytest.mark.asyncio
async def test_macos_ffmpeg_avfoundation_capture(clean_env):
    clean_env.setattr("sys.platform", "darwin")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only("ffmpeg"))
    payload = b"\xff\xd8\xff-jpeg"

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess(stdout=payload)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await get_camera_photo()

    assert result == payload
    cmd = seen_cmds[0]
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "avfoundation"
    assert "-i" in cmd and cmd[cmd.index("-i") + 1] == "0"


@pytest.mark.asyncio
async def test_linux_ffmpeg_v4l2_default_device(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only("ffmpeg"))
    payload = b"\xff\xd8\xff-jpeg"

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess(stdout=payload)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await get_camera_photo()

    assert result == payload
    cmd = seen_cmds[0]
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "v4l2"
    assert "-i" in cmd and cmd[cmd.index("-i") + 1] == "/dev/video0"


@pytest.mark.asyncio
async def test_linux_ffmpeg_explicit_device_overrides_default(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only("ffmpeg"))

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess(stdout=b"jpeg")

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        await get_camera_photo(device="/dev/video2")

    cmd = seen_cmds[0]
    assert cmd[cmd.index("-i") + 1] == "/dev/video2"


@pytest.mark.asyncio
async def test_windows_ffmpeg_uses_explicit_device_name(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only("ffmpeg"))

    seen_cmds: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        seen_cmds.append(list(args))
        return _FakeProcess(stdout=b"jpeg")

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await get_camera_photo(device="USB2.0 Camera")

    assert result == b"jpeg"
    # Only one call: explicit device skips the dshow enumeration probe.
    assert len(seen_cmds) == 1
    cmd = seen_cmds[0]
    assert cmd[cmd.index("-f") + 1] == "dshow"
    assert cmd[cmd.index("-i") + 1] == "video=USB2.0 Camera"


@pytest.mark.asyncio
async def test_windows_ffmpeg_auto_detects_device_from_dshow_listing(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only("ffmpeg"))
    listing = (
        b'[dshow @ 0000] "Integrated Webcam" (video)\n'
        b'[dshow @ 0000] "Microphone" (audio)\n'
    )

    def _make_proc(*args, **kwargs):
        cmd = list(args)
        if "-list_devices" in cmd:
            return _FakeProcess(stderr=listing, returncode=1)
        return _FakeProcess(stdout=b"jpeg")

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await get_camera_photo()

    assert result == b"jpeg"


@pytest.mark.asyncio
async def test_windows_ffmpeg_returns_none_when_no_device_detected(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only("ffmpeg"))

    def _make_proc(*args, **kwargs):
        return _FakeProcess(stderr=b"no video devices found", returncode=1)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await get_camera_photo()

    assert result is None


@pytest.mark.asyncio
async def test_capture_returns_none_on_nonzero_exit(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only("ffmpeg"))

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=b"", returncode=1)),
    ):
        result = await get_camera_photo()

    assert result is None


@pytest.mark.asyncio
async def test_subprocess_filenotfound_returns_none(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only("ffmpeg"))

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=FileNotFoundError("ffmpeg missing")),
    ):
        result = await get_camera_photo()

    assert result is None


@pytest.mark.asyncio
async def test_unexpected_exception_is_swallowed(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("zrb.llm.util.camera.shutil.which", _which_only("ffmpeg"))

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await get_camera_photo()

    assert result is None


# ---------------------------------------------------------------------------
# missing_tool_hint
# ---------------------------------------------------------------------------


def test_missing_tool_hint_termux(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)

    hint = missing_tool_hint()

    assert "termux-api" in hint


def test_missing_tool_hint_macos(clean_env):
    clean_env.setattr("sys.platform", "darwin")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)

    hint = missing_tool_hint()

    assert "ffmpeg" in hint
    assert "Camera" in hint


def test_missing_tool_hint_windows(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)

    hint = missing_tool_hint()

    assert "ffmpeg" in hint
    assert "dshow" in hint


def test_missing_tool_hint_wsl(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")

    hint = missing_tool_hint()

    assert "usbipd-win" in hint


def test_missing_tool_hint_generic_linux(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)

    hint = missing_tool_hint()

    assert "ffmpeg" in hint
    assert "video" in hint
