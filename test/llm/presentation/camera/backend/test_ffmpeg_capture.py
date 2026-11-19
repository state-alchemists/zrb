"""`AutoCameraBackend.capture`, and which ffmpeg command answers it.

Four platform answers sit behind one call: Windows' dshow device names, WSL
borrowing `ffmpeg.exe` across the boundary, WSL falling back to a `/dev/video*`
node the tunnel exposed, and plain v4l2. These tests pin the choice rather than
the pixels: which command runs first, and that a camera Windows listed is never
silently swapped for another one that happened to answer. The last three pin the
quieter contract — a capture that cannot happen returns `None` instead of
raising, whatever ffmpeg, the kernel or the stand-in process did.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.presentation.camera.backend import AutoCameraBackend

from .ffmpeg_support import FakeProcess as _FakeProcess
from .ffmpeg_support import record_procs as _record_procs
from .ffmpeg_support import which_only as _which_only


@pytest.mark.asyncio
async def test_windows_ffmpeg_auto_detects_device_from_dshow_listing(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
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
        result = await AutoCameraBackend().capture(None)

    assert result == b"jpeg"


@pytest.mark.asyncio
async def test_windows_ffmpeg_returns_none_when_no_device_detected(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))

    def _make_proc(*args, **kwargs):
        return _FakeProcess(stderr=b"no video devices found", returncode=1)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await AutoCameraBackend().capture(None)

    assert result is None


@pytest.mark.asyncio
async def test_wsl_captures_through_windows_ffmpeg_exe(clean_env):
    "Windows keeps the camera: WSL borrows it through ffmpeg.exe's dshow."
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg.exe"))
    commands, exec_mock = _record_procs(b'[dshow @ 0] "USB Camera" (video)\n')

    with patch("asyncio.create_subprocess_exec", new=exec_mock):
        result = await AutoCameraBackend().capture(None)

    assert result == b"jpeg"
    assert commands[-1][0] == "ffmpeg.exe"
    assert "video=USB Camera" in commands[-1]


@pytest.mark.asyncio
async def test_wsl_dev_video_device_uses_linux_ffmpeg(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg", "ffmpeg.exe"))
    commands, exec_mock = _record_procs()

    with patch("asyncio.create_subprocess_exec", new=exec_mock):
        result = await AutoCameraBackend().capture("/dev/video0")

    assert result == b"jpeg"
    assert commands == [commands[0]]
    assert commands[0][0] == "ffmpeg" and "v4l2" in commands[0]


@pytest.mark.asyncio
async def test_wsl_without_ffmpeg_exe_falls_back_to_v4l2(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    commands, exec_mock = _record_procs()

    with patch("asyncio.create_subprocess_exec", new=exec_mock):
        result = await AutoCameraBackend().capture(None)

    assert result == b"jpeg"
    assert "/dev/video0" in commands[0]


@pytest.mark.asyncio
async def test_wsl_falls_back_to_a_usbipd_camera_windows_no_longer_lists(clean_env):
    "A camera attached through usbipd leaves Windows' listing for /dev/video0."
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg", "ffmpeg.exe"))
    clean_env.setattr("glob.glob", lambda pattern: ["/dev/video0"])
    commands, exec_mock = _record_procs()

    with patch("asyncio.create_subprocess_exec", new=exec_mock):
        result = await AutoCameraBackend().capture(None)

    assert result == b"jpeg"
    assert commands[-1][0] == "ffmpeg" and "/dev/video0" in commands[-1]


@pytest.mark.asyncio
async def test_wsl_does_not_swap_a_busy_windows_camera_for_dev_video(clean_env):
    "A listed Windows camera that fails must not turn into another camera's photo."
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg", "ffmpeg.exe"))
    clean_env.setattr("glob.glob", lambda pattern: ["/dev/video0"])
    commands: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        commands.append(list(args))
        if "-list_devices" in args:
            return _FakeProcess(stderr=b'[dshow @ 0] "USB Camera" (video)\n')
        return _FakeProcess(stderr=b"Could not run graph", returncode=1)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await AutoCameraBackend().capture(None)

    assert result is None
    assert all(cmd[0] == "ffmpeg.exe" for cmd in commands)


@pytest.mark.asyncio
async def test_a_failed_dev_video_capture_on_wsl_gets_the_linux_hint(clean_env):
    "/photo /dev/video0 fails on Linux v4l2; the hint must not blame dshow."
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg", "ffmpeg.exe"))
    clean_env.setattr("glob.glob", lambda pattern: ["/dev/video0"])
    backend = AutoCameraBackend()

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=b"", returncode=1)),
    ):
        result = await backend.capture("/dev/video0")

    assert result is None
    hint = backend.get_failure_hint()
    assert "Captured through Windows ffmpeg.exe" not in hint
    assert "/dev/video* exists" in hint


@pytest.mark.asyncio
async def test_dev_video_on_wsl_without_linux_ffmpeg_asks_for_it(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg.exe"))
    backend = AutoCameraBackend()

    result = await backend.capture("/dev/video0")

    assert result is None
    hint = backend.get_failure_hint()
    assert "sudo apt install ffmpeg" in hint
    assert "Captured through Windows ffmpeg.exe" not in hint


@pytest.mark.asyncio
async def test_wsl_without_any_camera_stops_after_the_windows_listing(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg", "ffmpeg.exe"))
    clean_env.setattr("glob.glob", lambda pattern: [])
    commands, exec_mock = _record_procs()

    with patch("asyncio.create_subprocess_exec", new=exec_mock):
        result = await AutoCameraBackend().capture(None)

    assert result is None
    assert all(cmd[0] == "ffmpeg.exe" for cmd in commands)


@pytest.mark.asyncio
async def test_capture_returns_none_on_nonzero_exit(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=b"", returncode=1)),
    ):
        result = await AutoCameraBackend().capture(None)

    assert result is None


@pytest.mark.asyncio
async def test_subprocess_filenotfound_returns_none(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=FileNotFoundError("ffmpeg missing")),
    ):
        result = await AutoCameraBackend().capture(None)

    assert result is None


@pytest.mark.asyncio
async def test_unexpected_exception_is_swallowed(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "zrb.llm.presentation.camera.backend.auto.is_termux", lambda: False
    )
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await AutoCameraBackend().capture(None)

    assert result is None
