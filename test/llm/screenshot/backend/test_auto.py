"`AutoScreenshotBackend`: the capture chain and failure hint per platform."

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from zrb.llm.screenshot.backend import AutoScreenshotBackend


class _FakeProcess:
    def __init__(self, stdout: bytes = b"", stderr: bytes = b"", returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self._exit_code = returncode
        self.returncode: int | None = None

    async def communicate(self):
        self.returncode = self._exit_code
        return (self._stdout, self._stderr)

    def kill(self):
        self.returncode = -9

    async def wait(self):
        return self.returncode


@pytest.fixture
def platform(monkeypatch):
    "A Linux desktop with no session; each test sets up its own."
    for var in ("WSL_DISTRO_NAME", "WSLENV", "WAYLAND_DISPLAY", "DISPLAY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("zrb.config.helper.is_termux", lambda: False)
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    return monkeypatch


def _programs(ran: list[str], working: set[str]):
    "Run each program, recording it; only those in *working* write an image."

    def _make_proc(*args, **kwargs):
        ran.append(args[0])
        if args[0] not in working:
            return _FakeProcess(stderr=b"no luck", returncode=1)
        if args[0].startswith("powershell"):
            return _FakeProcess(stdout=base64.b64encode(b"shot"))
        with open(args[-1], "wb") as image_file:
            image_file.write(b"shot")
        return _FakeProcess()

    return AsyncMock(side_effect=_make_proc)


def _no_pillow(**kwargs):
    raise OSError("cannot grab")


async def _capture(working: set[str]) -> tuple[bytes | None, list[str], str]:
    ran: list[str] = []
    backend = AutoScreenshotBackend()
    with patch("asyncio.create_subprocess_exec", new=_programs(ran, working)):
        data = await backend.capture(None)
    return data, ran, backend.get_failure_hint()


@pytest.mark.asyncio
async def test_macos_uses_screencapture(platform):
    platform.setattr("sys.platform", "darwin")

    data, ran, _ = await _capture({"screencapture"})

    assert (data, ran) == (b"shot", ["screencapture"])


@pytest.mark.asyncio
async def test_macos_failure_points_at_screen_recording_permission(platform):
    platform.setattr("sys.platform", "darwin")

    data, _, hint = await _capture(set())

    assert data is None
    assert "Screen Recording" in hint
    assert "screencapture: no luck" in hint


@pytest.mark.asyncio
async def test_windows_uses_pillow_first(platform):
    platform.setattr("sys.platform", "win32")
    platform.setattr("PIL.ImageGrab.grab", lambda **kwargs: Image.new("RGB", (4, 4)))

    data, ran, _ = await _capture(set())

    assert data is not None
    assert ran == []


@pytest.mark.asyncio
async def test_windows_falls_back_to_powershell(platform):
    platform.setattr("sys.platform", "win32")
    platform.setattr("PIL.ImageGrab.grab", _no_pillow)

    data, ran, _ = await _capture({"powershell"})

    assert (data, ran) == (b"shot", ["powershell"])


@pytest.mark.asyncio
async def test_windows_failure_lists_both_attempts(platform):
    platform.setattr("sys.platform", "win32")
    platform.setattr("PIL.ImageGrab.grab", _no_pillow)

    _, _, hint = await _capture(set())

    assert "interactive desktop" in hint
    assert "pillow: cannot grab" in hint
    assert "powershell: no luck" in hint


@pytest.mark.asyncio
async def test_wsl_captures_the_windows_desktop(platform):
    platform.setenv("WSL_DISTRO_NAME", "Ubuntu")
    platform.setenv("DISPLAY", ":0")

    data, ran, _ = await _capture({"powershell.exe"})

    assert (data, ran) == (b"shot", ["powershell.exe"])


@pytest.mark.asyncio
async def test_wsl_failure_explains_interop(platform):
    platform.setenv("WSL_DISTRO_NAME", "Ubuntu")

    _, _, hint = await _capture(set())

    assert "powershell.exe" in hint
    assert "interop" in hint


@pytest.mark.asyncio
async def test_wayland_tries_grim_then_the_desktop_tools(platform):
    platform.setenv("WAYLAND_DISPLAY", "wayland-0")
    platform.setenv("DISPLAY", ":0")

    data, ran, _ = await _capture({"spectacle"})

    assert data == b"shot"
    assert ran == ["grim", "gnome-screenshot", "spectacle"]


@pytest.mark.asyncio
async def test_wayland_never_falls_back_to_x11_grabbers(platform):
    platform.setenv("XDG_SESSION_TYPE", "wayland")
    platform.setenv("DISPLAY", ":0")
    grabbed: list = []
    platform.setattr("PIL.ImageGrab.grab", lambda **kwargs: grabbed.append(kwargs))

    data, ran, hint = await _capture(set())

    assert data is None
    assert ran == ["grim", "gnome-screenshot", "spectacle"]
    assert grabbed == []
    assert "Install grim" in hint


@pytest.mark.asyncio
async def test_x11_tries_pillow_then_the_programs(platform):
    platform.setenv("DISPLAY", ":0")
    platform.setattr("PIL.ImageGrab.grab", _no_pillow)

    data, ran, _ = await _capture({"import"})

    assert data == b"shot"
    assert ran == ["scrot", "import"]


@pytest.mark.asyncio
async def test_x11_failure_suggests_a_program(platform):
    platform.setenv("DISPLAY", ":0")
    platform.setattr("PIL.ImageGrab.grab", _no_pillow)

    _, ran, hint = await _capture(set())

    assert ran == ["scrot", "import", "gnome-screenshot", "spectacle"]
    assert "Install scrot" in hint


@pytest.mark.asyncio
async def test_without_a_graphical_session_nothing_runs(platform):
    data, ran, hint = await _capture(set())

    assert (data, ran) == (None, [])
    assert "No graphical session" in hint


@pytest.mark.asyncio
async def test_termux_cannot_capture_and_says_so(platform):
    platform.setattr("zrb.config.helper.is_termux", lambda: True)
    platform.setenv("DISPLAY", ":0")

    data, ran, hint = await _capture({"scrot"})

    assert (data, ran) == (None, [])
    assert "/attach" in hint


@pytest.mark.parametrize(
    "setup, displays",
    [
        ({"sys.platform": "darwin"}, ["1", "2"]),
        ({"sys.platform": "win32"}, ["all"]),
        ({"env": "WSL_DISTRO_NAME"}, ["all"]),
        ({}, []),
        ({"termux": True}, []),
    ],
)
def test_display_completion_per_platform(platform, setup, displays):
    if "sys.platform" in setup:
        platform.setattr("sys.platform", setup["sys.platform"])
    if "env" in setup:
        platform.setenv(setup["env"], "Ubuntu")
    if setup.get("termux"):
        platform.setattr("zrb.config.helper.is_termux", lambda: True)

    assert AutoScreenshotBackend().list_displays() == displays


def test_the_auto_backend_is_named_auto():
    assert AutoScreenshotBackend().name == "auto"
