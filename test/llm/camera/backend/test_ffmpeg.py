"`FfmpegCameraBackend` device listing and the failure hints."

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.camera.backend import AutoCameraBackend, FfmpegCameraBackend


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
async def test_windows_ffmpeg_auto_detects_device_from_dshow_listing(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
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
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))

    def _make_proc(*args, **kwargs):
        return _FakeProcess(stderr=b"no video devices found", returncode=1)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await AutoCameraBackend().capture(None)

    assert result is None


def _record_procs(listing: bytes = b""):
    "A `create_subprocess_exec` stand-in recording each command it runs."
    commands: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        commands.append(list(args))
        if "-list_devices" in args:
            return _FakeProcess(stderr=listing, returncode=1)
        return _FakeProcess(stdout=b"jpeg")

    return commands, AsyncMock(side_effect=_make_proc)


@pytest.mark.asyncio
async def test_wsl_captures_through_windows_ffmpeg_exe(clean_env):
    "Windows keeps the camera: WSL borrows it through ffmpeg.exe's dshow."
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
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
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
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
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
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
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg", "ffmpeg.exe"))
    clean_env.setattr("glob.glob", lambda pattern: ["/dev/video0"])
    commands, exec_mock = _record_procs()

    with patch("asyncio.create_subprocess_exec", new=exec_mock):
        result = await AutoCameraBackend().capture(None)

    assert result == b"jpeg"
    assert commands[-1][0] == "ffmpeg" and "/dev/video0" in commands[-1]


@pytest.mark.asyncio
async def test_a_failed_dev_video_capture_on_wsl_gets_the_linux_hint(clean_env):
    "/photo /dev/video0 fails on Linux v4l2; the hint must not blame dshow."
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
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
async def test_wsl_without_any_camera_stops_after_the_windows_listing(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
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
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
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
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
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
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await AutoCameraBackend().capture(None)

    assert result is None


def test_failure_hint_termux(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)

    hint = AutoCameraBackend().get_failure_hint()

    assert "termux-api" in hint


def test_failure_hint_macos(clean_env):
    clean_env.setattr("sys.platform", "darwin")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)

    hint = AutoCameraBackend().get_failure_hint()

    assert "ffmpeg" in hint
    assert "Camera" in hint


def test_failure_hint_windows(clean_env):
    clean_env.setattr("sys.platform", "win32")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)

    hint = AutoCameraBackend().get_failure_hint()

    assert "ffmpeg" in hint
    assert "dshow" in hint


def test_failure_hint_wsl_no_ffmpeg_exe_recommends_windows_ffmpeg(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only())
    clean_env.setattr("glob.glob", lambda pattern: [])

    hint = AutoCameraBackend().get_failure_hint()

    assert "winget install Gyan.FFmpeg" in hint
    assert "usbipd-win" in hint and "kernel" in hint


def test_failure_hint_wsl_device_exists(clean_env):
    "/dev/video0 exists -- driver is fine, the USB/IP tunnel is the problem."
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg"))
    clean_env.setattr("glob.glob", lambda pattern: ["/dev/video0"])

    hint = AutoCameraBackend().get_failure_hint()

    assert "USB/IP" in hint
    assert "external USB webcam" in hint
    assert "ffmpeg.exe" in hint


def test_failure_hint_wsl_with_ffmpeg_exe_points_at_dshow(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    clean_env.setattr("shutil.which", _which_only("ffmpeg.exe"))

    hint = AutoCameraBackend().get_failure_hint()

    assert "ffmpeg.exe -f dshow -list_devices true" in hint
    assert "usbipd" not in hint


def test_failure_hint_generic_linux(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)

    hint = AutoCameraBackend().get_failure_hint()

    assert "ffmpeg" in hint
    assert "video" in hint


def test_list_devices_termux_uses_camera_ids(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: True)

    assert AutoCameraBackend().list_devices() == ["0", "1"]


def test_list_devices_linux_globs_video_nodes(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("sys.platform", "linux")
    clean_env.setattr(
        "glob.glob",
        lambda pattern: ["/dev/video1", "/dev/video0"],
    )

    assert AutoCameraBackend().list_devices() == ["/dev/video0", "/dev/video1"]


def test_list_devices_windows_sync_never_blocks(clean_env):
    "Windows dshow names need the ffmpeg subprocess probe; the sync path"
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("sys.platform", "win32")

    assert AutoCameraBackend().list_devices() == []


@pytest.mark.asyncio
async def test_refresh_devices_parses_dshow_names_on_windows(clean_env):
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
        devices = await FfmpegCameraBackend().refresh_devices()

    assert devices == ["Integrated Webcam", "USB Camera"]


@pytest.mark.asyncio
async def test_refresh_devices_on_wsl_lists_windows_and_linux_cameras(clean_env):
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
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
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
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
    clean_env.setattr("zrb.config.helper.is_termux", lambda: False)
    clean_env.setattr("sys.platform", "win32")
    backend = FfmpegCameraBackend()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_probe(self):
        started.set()
        await release.wait()
        self._device_cache["time"] = time.monotonic()
        self._device_cache["devices"] = ["USB Camera"]

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
