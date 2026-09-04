"""Public-API tests for camera photo capture.

All paths exercise `get_camera_photo()` and `missing_tool_hint()`. Per
AGENTS.md, no underscore-prefixed helpers are touched directly. External
dependencies (termux-camera-photo, ffmpeg, the live filesystem) are mocked.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.util.camera import (
    get_camera_photo,
    list_camera_devices,
    maybe_refresh_camera_devices,
    missing_tool_hint,
    refresh_camera_devices,
)


@pytest.fixture
def clean_env(monkeypatch):
    """Strip every camera-relevant env var before each test."""
    for var in ("WSL_DISTRO_NAME", "WSLENV"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class _FakeProcess:
    """Minimal async-process stand-in for `asyncio.create_subprocess_exec`."""

    def __init__(
        self,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        hang_seconds: float = 0,
    ):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self._hang_seconds = hang_seconds
        self.killed = False

    async def communicate(self):
        if self._hang_seconds:
            await asyncio.sleep(self._hang_seconds)
        return (self._stdout, self._stderr)

    def kill(self):
        self.killed = True

    async def wait(self):
        return self.returncode


def _which_only(*names: str):
    """Return a `shutil.which` stand-in that only "finds" the given names."""

    def _which(name: str):
        return f"/usr/bin/{name}" if name in names else None

    return _which


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


def test_missing_tool_hint_wsl_no_device(clean_env):
    """No /dev/video* at all -- usbipd attached the USB device, but the stock
    WSL2 kernel has no camera driver, so no device node ever appears."""
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("zrb.llm.util.camera.glob.glob", lambda pattern: [])

    hint = missing_tool_hint()

    assert "usbipd-win" in hint
    assert "custom" in hint.lower() and "kernel" in hint.lower()


def test_missing_tool_hint_wsl_device_exists(clean_env):
    """/dev/video0 exists -- driver is fine, the USB/IP tunnel is the problem."""
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("zrb.llm.util.camera.glob.glob", lambda pattern: ["/dev/video0"])

    hint = missing_tool_hint()

    assert "USB/IP" in hint
    assert "external USB webcam" in hint


def test_missing_tool_hint_generic_linux(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)

    hint = missing_tool_hint()

    assert "ffmpeg" in hint
    assert "video" in hint


def test_list_camera_devices_termux_uses_camera_ids(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)

    assert list_camera_devices(cache={}) == ["0", "1"]


def test_list_camera_devices_linux_globs_video_nodes(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.util.camera.glob.glob",
        lambda pattern: ["/dev/video1", "/dev/video0"],
    )

    # Sorted, so device order is stable in the completion dropdown.
    assert list_camera_devices(cache={}) == ["/dev/video0", "/dev/video1"]


def test_list_camera_devices_windows_sync_never_blocks(clean_env):
    """Windows dshow names need the ffmpeg subprocess probe; the sync path
    must return immediately (empty) and leave population to the async
    refresh, so completion never blocks a keystroke."""
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("sys.platform", "win32")

    assert list_camera_devices(cache={}) == []


@pytest.mark.asyncio
async def test_refresh_camera_devices_parses_dshow_names_on_windows(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("sys.platform", "win32")

    listing = (
        '[dshow @ 0000] "Integrated Webcam" (video)\n'
        '[dshow @ 0000] "Microphone" (audio)\n'
        '[dshow @ 0000] "USB Camera" (video)\n'
    )

    def _make_proc(*args, **kwargs):
        return _FakeProcess(stderr=listing.encode())

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        devices = await refresh_camera_devices(cache={})

    # Audio devices are excluded; only video entries survive.
    assert devices == ["Integrated Webcam", "USB Camera"]


@pytest.mark.asyncio
async def test_maybe_refresh_camera_devices_schedules_probe_when_stale(clean_env):
    """Stale cache + a running loop → a background refresh is scheduled and
    the cache is repopulated without blocking the caller."""
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("sys.platform", "win32")
    cache: dict = {}

    def _make_proc(*args, **kwargs):
        return _FakeProcess(stderr=b'[dshow @ 0] "USB Camera" (video)\n')

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        task = maybe_refresh_camera_devices(cache)
        assert task is not None
        # Deterministic: await the scheduled refresh instead of hoping a
        # couple of loop ticks are enough (they weren't on CI).
        await task

    assert cache.get("refreshing") is False
    assert cache.get("devices") == ["USB Camera"]
    # Fresh cache → no new refresh scheduled.
    assert maybe_refresh_camera_devices(cache) is None


def test_list_camera_devices_caches_per_caller_dict(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)

    cache: dict = {}
    first = list_camera_devices(cache=cache)
    second = list_camera_devices(cache=cache)

    assert first == second == ["0", "1"]
    assert "devices" in cache
