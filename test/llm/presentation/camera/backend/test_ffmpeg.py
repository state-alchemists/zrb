"`FfmpegCameraBackend` device listing and the failure hints."

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.presentation.camera.backend import AutoCameraBackend, FfmpegCameraBackend

from .ffmpeg_support import FakeProcess as _FakeProcess
from .ffmpeg_support import record_procs as _record_procs
from .ffmpeg_support import which_only as _which_only


def test_failure_hint_termux(clean_env):
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: True
    )

    hint = AutoCameraBackend().get_failure_hint()

    assert "termux-api" in hint


def test_failure_hint_macos(clean_env):
    clean_env.setattr("sys.platform", "darwin")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )

    hint = AutoCameraBackend().get_failure_hint()

    assert "ffmpeg" in hint
    assert "Camera" in hint


def test_failure_hint_windows(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )

    hint = AutoCameraBackend().get_failure_hint()

    assert "ffmpeg" in hint
    assert "dshow" in hint


def test_failure_hint_wsl_no_ffmpeg_exe_recommends_windows_ffmpeg(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only())
    clean_env.setattr("glob.glob", lambda pattern: [])

    hint = AutoCameraBackend().get_failure_hint()

    assert "winget install Gyan.FFmpeg" in hint
    assert "usbipd-win" in hint and "kernel" in hint


def test_failure_hint_wsl_device_exists(clean_env):
    "/dev/video0 exists -- driver is fine, the USB/IP tunnel is the problem."
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    clean_env.setattr("glob.glob", lambda pattern: ["/dev/video0"])

    hint = AutoCameraBackend().get_failure_hint()

    assert "USB/IP" in hint
    assert "external USB webcam" in hint
    assert "ffmpeg.exe" in hint


def test_failure_hint_wsl_with_ffmpeg_exe_points_at_dshow(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg.exe"))

    hint = AutoCameraBackend().get_failure_hint()

    assert "ffmpeg.exe -f dshow -list_devices true" in hint
    assert "usbipd" not in hint


def test_failure_hint_generic_linux(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )

    hint = AutoCameraBackend().get_failure_hint()

    assert "ffmpeg" in hint
    assert "video" in hint


def test_list_devices_termux_uses_camera_ids(clean_env):
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: True
    )

    assert AutoCameraBackend().list_devices() == ["0", "1"]


def test_list_devices_linux_globs_video_nodes(clean_env):
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "glob.glob",
        lambda pattern: ["/dev/video1", "/dev/video0"],
    )

    assert AutoCameraBackend().list_devices() == ["/dev/video0", "/dev/video1"]


def test_list_devices_windows_sync_never_blocks(clean_env):
    "Windows dshow names need the ffmpeg subprocess probe; the sync path"
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("sys.platform", "win32")

    assert AutoCameraBackend().list_devices() == []


@pytest.mark.asyncio
async def test_refresh_devices_parses_dshow_names_on_windows(clean_env):
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("sys.platform", "win32")

    listing = (
        '[dshow @ 0000] "Integrated Webcam" (video)\n'
        '[dshow @ 0000] "Microphone" (audio)\n'
        '[dshow @ 0000] "USB Camera" (video)\n'
    )

    def _make_proc(*args, **kwargs):
        return _FakeProcess(stderr=listing.encode())

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        devices = await FfmpegCameraBackend().refresh_devices()

    assert devices == ["Integrated Webcam", "USB Camera"]


@pytest.mark.asyncio
async def test_refresh_devices_on_wsl_lists_windows_and_linux_cameras(clean_env):
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("sys.platform", "linux")
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg.exe"))
    clean_env.setattr("glob.glob", lambda pattern: ["/dev/video0"])
    _, exec_mock = _record_procs(b'[dshow @ 0] "USB Camera" (video)\n')

    with patch("asyncio.create_subprocess_exec", new=exec_mock):
        devices = await FfmpegCameraBackend().refresh_devices()

    assert devices == ["USB Camera", "/dev/video0"]


@pytest.mark.asyncio
async def test_schedule_device_refresh_schedules_probe_when_stale(clean_env):
    "Stale cache + a running loop → a background refresh is scheduled and"
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("sys.platform", "win32")
    backend = FfmpegCameraBackend()

    def _make_proc(*args, **kwargs):
        return _FakeProcess(stderr=b'[dshow @ 0] "USB Camera" (video)\n')

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        task = backend.schedule_device_refresh()
        assert task is not None

        await task

    assert backend.list_devices() == ["USB Camera"]

    assert backend.schedule_device_refresh() is None


def test_list_devices_serves_the_cache_until_it_is_stale(clean_env):
    clean_env.setattr("sys.platform", "linux")
    globbed = [["/dev/video0"], ["/dev/video0", "/dev/video1"]]
    clean_env.setattr("glob.glob", lambda pattern: globbed.pop(0))
    backend = FfmpegCameraBackend()

    assert backend.list_devices() == ["/dev/video0"]

    assert backend.list_devices() == ["/dev/video0"]


@pytest.mark.asyncio
async def test_a_scheduled_probe_runs_to_completion_and_is_not_scheduled_twice(
    clean_env,
):
    "The dshow listing is slow, so `list_devices` starts it in the background"
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("sys.platform", "win32")
    backend = FfmpegCameraBackend()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_probe(self):
        started.set()
        await release.wait()
        self._cache_devices(["USB Camera"])

    with patch.object(FfmpegCameraBackend, "refresh_devices", new=slow_probe):
        assert backend.list_devices() == []
        await asyncio.wait_for(started.wait(), 5)

        assert backend.schedule_device_refresh() is None
        release.set()
        for _ in range(100):
            if backend.list_devices() == ["USB Camera"]:
                break
            await asyncio.sleep(0)

    assert backend.list_devices() == ["USB Camera"]

    assert backend.schedule_device_refresh() is None
